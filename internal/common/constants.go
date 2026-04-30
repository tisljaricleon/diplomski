package common

// Labels
const CommonPrefix = "common/"
const ImageTypeLabel = "image-type"
const UseMPSLabel = "use-mps"

const FlPrefix = "fl/"
const FlTypeLabel = "type"
const NumPartitionsLabel = "num-partitions"
const PartitionIdLabel = "partition-id"
const CommunicationCostPrefix = "comm/"
const DataDistributionPrefix = "data/"

const InfProxyPrefix = "inf-proxy/"
const ProxyNodePortLabel = "node-port"


// Node image type labels
const IMAGE_TYPE_RPI = "rpi"
const IMAGE_TYPE_JETSON = "jetson"

// Container images
const FL_RPI_IMAGE = "leontisljaric/fl-rpi:0.1"
const FL_JETSON_IMAGE = "leontisljaric/fl-jetson:0.1"
const INF_SERVICE_RPI_IMAGE = "leontisljaric/inf-service-rpi:0.1"
const INF_SERVICE_JETSON_IMAGE = "leontisljaric/inf-service-jetson:0.1"
const INF_PROXY_RPI_IMAGE = "leontisljaric/inf-proxy-rpi:0.1"
const INF_PROXY_JETSON_IMAGE = "leontisljaric/inf-proxy-jetson:0.1"

// Component prefixes
const FL_GLOBAL_AGG_PREFIX = "fl-gl"
const FL_LOCAL_AGG_PREFIX = "fl-la"
const FL_CLIENT_PREFIX = "fl-cl"
const INF_SERVICE_PREFIX = "inf-service"
const INF_PROXY_PREFIX = "inf-proxy"

// Prefixes for Kubernetes resources
const DEPLOYMENT_PREFIX = "dep"
const CONFIG_MAP_PREFIX = "cm"
const PV_PREFIX = "pv"
const PVC_PREFIX = "pvc"
const SERVICE_PREFIX = "svc"

// Internal ports
const FL_AGG_PORT = 8080
const INF_SERVICE_PORT = 8000
const INF_PROXY_PORT = 80

// Persistent volume
const BASE_PV_PATH = "/mnt/aiotwin/pv"
const PVC_STORAGE_SIZE = "2Gi"

// FL types
const FL_TYPE_CLIENT = "client"
const FL_TYPE_LOCAL_AGGREGATOR = "local_aggregator"
const FL_TYPE_GLOBAL_AGGREGATOR = "global_aggregator"

// Events
const NODE_STATE_CHANGE_EVENT_TYPE = "NodeStateChanged"
const FL_FINISHED_EVENT_TYPE = "FlFinished"

// Node states
const NODE_ADDED = "ADDED"
const NODE_REMOVED = "REMOVED"
