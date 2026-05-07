local http    = require "resty.http"
local cjson   = require "cjson.safe"
local counter = ngx.shared.request_counter


local local_service_url  = os.getenv("LOCAL_SERVICE_URL")  or ""
local parent_service_url = os.getenv("PARENT_SERVICE_URL") or ""
local max_inflight       = tonumber(os.getenv("MAX_INFLIGHT")) or 200


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
    local inflight = counter:get("inflight") or 0
    local is_training = false

    local http_client = http.new()
    http_client:set_timeout(500)

    local training_response, training_error = http_client:request_uri("http://localhost:8001/trainingMetrics", { method = "GET" })
    if not (training_response and training_response.status == 200) then
        ngx.log(ngx.WARN, "[http server] Failed to fetch /trainingMetrics: ", training_error)
    else
        local training_payload = cjson.decode(training_response.body)
        if training_payload and training_payload.data and training_payload.data.is_training == true then
            is_training = true
        end
    end

    local device_response, device_error = http_client:request_uri("http://localhost:8001/deviceMetrics", { method = "GET" })
    if not (device_response and device_response.status == 200) then
        ngx.log(ngx.WARN, "[http server] Failed to fetch /deviceMetrics: ", device_error)
    end

    if is_training and inflight > 25 then
        target_url = parent_service_url
    end


end

ngx.log(ngx.WARN, "[proxy] target_url=", target_url, " inflight=", counter:get("inflight") or 0)


counter:incr("inflight", 1, 0)

local upstream_client = http.new()
upstream_client:set_timeout(25000)
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

ngx.log(ngx.WARN, "[proxy] upstream_status=", upstream_request.status, " target_url=", target_url)


ngx.status = upstream_request.status
for k, v in pairs(upstream_request.headers) do
    local lk = k:lower()
    if lk ~= "transfer-encoding" and lk ~= "connection" and lk ~= "keep-alive" then
        ngx.header[k] = v
    end
end

ngx.print(upstream_request.body)
