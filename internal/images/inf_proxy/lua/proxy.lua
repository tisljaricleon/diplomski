local http    = require "resty.http"
local cjson   = require "cjson.safe"
local counter = ngx.shared.inflight_60s_avg


local local_service_url  = os.getenv("LOCAL_SERVICE_URL")  or ""
local parent_service_url = os.getenv("PARENT_SERVICE_URL") or ""
local max_inflight       = tonumber(os.getenv("MAX_INFLIGHT")) or 99999
local training_refresh_s = (tonumber(os.getenv("TRAINING_METRICS_REFRESH_MS")) or 1000) / 1000
local inflight           = counter:get("inflight") or 0
local avg_inflight       = (function()
    local total, count, now = 0, 0, ngx.now()
    for i = 0, 59 do
        local t = counter:get("s_t_" .. i)
        local v = counter:get("s_v_" .. i)
        if t and v and (now - t) <= 60 then total = total + v; count = count + 1 end
    end
    return count > 0 and (total / count) or 0
end)()
local is_training        = false


local target_url = nil
if local_service_url == "" then
    ngx.status = 502
    ngx.header.content_type = "application/json"
    ngx.say(cjson.encode({ error = "No local service configured" }))
    return
else
    target_url = local_service_url
end


if parent_service_url ~= "" then
    local now = ngx.now()
    local last_fetch = counter:get("training_last_fetch") or 0

    local cached_training = counter:get("training_is_training")
    if cached_training ~= nil then
        is_training = (cached_training == 1)
    end

    if (now - last_fetch) >= training_refresh_s then
        local got_lock = counter:add("training_fetch_lock", 1, 0.2)
        if got_lock then
            local http_client = http.new()
            http_client:set_timeout(120)

            local training_response, training_error = http_client:request_uri("http://127.0.0.1:8001/trainingMetrics", { method = "GET" })
            if not (training_response and training_response.status == 200) then
                ngx.log(ngx.WARN, "[http server] Failed to fetch /trainingMetrics: ", training_error)
            else
                local training_payload = cjson.decode(training_response.body)
                local fetched_training = false
                if training_payload and training_payload.data and training_payload.data.is_training == true then
                    fetched_training = true
                end
                counter:set("training_is_training", fetched_training and 1 or 0)
            end

            counter:set("training_last_fetch", now)
            counter:delete("training_fetch_lock")
        end
    end

    local cached_training_after = counter:get("training_is_training")
    if cached_training_after ~= nil then
        is_training = (cached_training_after == 1)
    end

    if is_training and avg_inflight > max_inflight then
        target_url = parent_service_url
    end


end

local last_target = counter:get("last_target") or ""
if last_target ~= target_url then
    ngx.log(ngx.WARN, "[proxy] SWITCHED ", last_target == "" and "(init)" or last_target, " -> ", target_url, " avg_inflight=", avg_inflight, " is_training=", tostring(is_training))
    counter:set("last_target", target_url)
end


counter:incr("inflight", 1, 0)

local upstream_client = http.new()
upstream_client:set_timeout(60000)
local body = ngx.req.get_body_data()
local headers = ngx.req.get_headers()

local upstream_request, upstream_error = upstream_client:request_uri(
    target_url .. "/predict",
    {
        method  = ngx.req.get_method(),
        headers = headers,
        body    = body,
    }
)

counter:incr("inflight", -1, 0)

if not upstream_request then
    ngx.log(ngx.ERR, "[proxy] Upstream error: ", upstream_error)
    ngx.status = 502
    ngx.header.content_type = "application/json"
    ngx.say(cjson.encode({ error = "Upstream error: " .. upstream_error }))
    return
end


ngx.status = upstream_request.status
for k, v in pairs(upstream_request.headers) do
    local lk = k:lower()
    if lk ~= "transfer-encoding" and lk ~= "connection" and lk ~= "keep-alive" then
        ngx.header[k] = v
    end
end

ngx.print(upstream_request.body)
