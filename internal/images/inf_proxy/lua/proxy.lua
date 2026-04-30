--[[
  proxy.lua — OpenResty routing + proxying logic

  Environment variables (injected via K8s ConfigMap / env):
    LOCAL_STATUS_URL   : HTTP URL to poll for local serving status, e.g. http://fl-cl-serving-0-svc:8000/status
    LOCAL_SERVING_URL  : Base URL of local inference container,      e.g. http://fl-cl-serving-0-svc:8000
    FALLBACK_URLS      : Comma-separated list of fallback nginx proxy base URLs (may be empty)
    MAX_REQUESTS       : Integer threshold; if ongoing_requests >= this AND training is active → redirect
--]]

local http    = require "resty.http"
local cjson   = require "cjson.safe"

-- ── Configuration ────────────────────────────────────────────────────────────

local local_status_url  = os.getenv("LOCAL_STATUS_URL")  or "http://127.0.0.1:8000/status"
local local_serving_url = os.getenv("LOCAL_SERVING_URL") or "http://127.0.0.1:8000"
local max_requests      = tonumber(os.getenv("MAX_REQUESTS")) or 200

local fallback_urls = {}
local fallback_str  = os.getenv("FALLBACK_URLS") or ""
for url in fallback_str:gmatch("[^,]+") do
    url = url:match("^%s*(.-)%s*$")   -- trim whitespace
    if url ~= "" then
        table.insert(fallback_urls, url)
    end
end

-- ── Shared counters ──────────────────────────────────────────────────────────

local counter = ngx.shared.request_counter

-- ── Routing decision ─────────────────────────────────────────────────────────

local target_url = local_serving_url   -- default: serve locally

if #fallback_urls > 0 then
    -- Poll the local serving container's /status endpoint
    local status_client = http.new()
    status_client:set_timeout(400)   -- 400 ms — fast check; if it times out we stay local

    local res, err = status_client:request_uri(local_status_url, { method = "GET" })

    if res and res.status == 200 then
        local data, decode_err = cjson.decode(res.body)
        if data then
            local ongoing   = tonumber(data.ongoing_requests) or 0
            local training  = data.training_active == true

            if ongoing >= max_requests and training then
                -- Round-robin across fallback nodes
                local idx = (counter:incr("fallback_rr", 1, 0) - 1) % #fallback_urls
                target_url = fallback_urls[idx + 1]
                ngx.log(ngx.INFO, string.format(
                    "[proxy] redirecting: ongoing=%d training=%s → %s",
                    ongoing, tostring(training), target_url
                ))
            end
        end
    else
        ngx.log(ngx.WARN, "[proxy] status check failed (", err or "non-200", "), using local serving")
    end
end

-- ── Track in-flight requests ─────────────────────────────────────────────────

counter:incr("inflight", 1, 0)

-- ── Read and buffer the request body (needed for multipart uploads) ───────────

ngx.req.read_body()
local body = ngx.req.get_body_data()

if not body then
    -- Body was spooled to a temp file (large upload)
    local body_file = ngx.req.get_body_file()
    if body_file then
        local f = io.open(body_file, "rb")
        if f then
            body = f:read("*a")
            f:close()
        end
    end
end

-- ── Forward request to chosen upstream ───────────────────────────────────────

local upstream_client = http.new()
upstream_client:set_timeout(30000)   -- 30 s for inference

local req_headers = ngx.req.get_headers()
req_headers["Host"] = nil            -- let resty.http derive Host from the URL

local upstream_res, upstream_err = upstream_client:request_uri(
    target_url .. "/predict",
    {
        method  = ngx.req.get_method(),
        headers = req_headers,
        body    = body,
    }
)

-- Decrement in-flight counter regardless of outcome
counter:incr("inflight", -1, 0)

if not upstream_res then
    ngx.log(ngx.ERR, "[proxy] upstream error: ", upstream_err)
    ngx.status = 502
    ngx.header.content_type = "application/json"
    ngx.say(cjson.encode({ error = "upstream error: " .. (upstream_err or "unknown") }))
    return
end

-- ── Stream response back to client ───────────────────────────────────────────

ngx.status = upstream_res.status

for k, v in pairs(upstream_res.headers) do
    local lk = k:lower()
    -- Skip hop-by-hop headers that must not be forwarded
    if lk ~= "transfer-encoding" and lk ~= "connection" and lk ~= "keep-alive" then
        ngx.header[k] = v
    end
end

ngx.print(upstream_res.body)
