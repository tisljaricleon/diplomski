package common

import (
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/events"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/model"
)

func GetNodeStateChangeEvent(availableNodesCurrent map[string]*model.Node, availableNodesNew map[string]*model.Node) events.Event {
	nodesAdded := []*model.Node{}
	// check for added nodes
	for _, node := range availableNodesNew {
		_, found := availableNodesCurrent[node.Id]
		if !found {
			nodesAdded = append(nodesAdded, node)
		}
	}

	nodesRemoved := []*model.Node{}
	// check for removed nodes
	for _, node := range availableNodesCurrent {
		_, found := availableNodesNew[node.Id]
		if !found {
			nodesRemoved = append(nodesRemoved, node)
		}
	}

	var event events.Event
	if len(nodesAdded) > 0 || len(nodesRemoved) > 0 {
		event = events.Event{
			Type:      NODE_STATE_CHANGE_EVENT_TYPE,
			Timestamp: time.Now(),
			Data: events.NodeStateChangeEvent{
				NodesAdded:   nodesAdded,
				NodesRemoved: nodesRemoved,
			},
		}
	}

	return event
}

func GetClientsAndAggregators(nodes []*model.Node) (*model.Node, []*model.Node, []*model.Node) {
	clients := []*model.Node{}
	localAggregators := []*model.Node{}
	globalAggregator := &model.Node{}
	for _, node := range nodes {
		switch node.Labels.Fl.Type {
		case FL_TYPE_GLOBAL_AGGREGATOR:
			globalAggregator = node
		case FL_TYPE_LOCAL_AGGREGATOR:
			localAggregators = append(localAggregators, node)
		case FL_TYPE_CLIENT:
			clients = append(clients, node)
		}
	}

	sort.Slice(localAggregators, func(i, j int) bool {
		compare := strings.Compare(localAggregators[i].Id, localAggregators[j].Id)
		if compare == -1 {
			return true
		} else {
			return false
		}
	})

	return globalAggregator, localAggregators, clients
}

func ClientNodesToFlClients(clients []*model.Node, flAggregator *model.FlAggregator, epochs int32) []*model.FlClient {
	flClients := []*model.FlClient{}
	for _, client := range clients {
		flClient := &model.FlClient{
			Id:               client.Id,
			ParentAddress:    flAggregator.ExternalAddress,
			ParentNodeId:     flAggregator.Id,
			Epochs:           epochs,
			DataDistribution: client.Labels.Fl.DataDistribution,
			NumPartitions:    client.Labels.Fl.NumPartitions,
			PartitionId:      client.Labels.Fl.PartitionId,
		}

		flClients = append(flClients, flClient)
	}

	return flClients
}

func GetClientInArray(clients []*model.FlClient, clientId string) *model.FlClient {
	for _, client := range clients {
		if client.Id == clientId {
			return client
		}
	}

	return &model.FlClient{}
}

func CalculateAverageFloat64(numbers []float64) float64 {
	if len(numbers) == 0 {
		return 0
	}

	var sum float64
	for _, number := range numbers {
		sum += number
	}

	return sum / float64(len(numbers))
}



// FL resource name helpers
func GetPVPath(nodeId string) string {
	return fmt.Sprintf("%s/%s", BASE_PV_PATH, nodeId)
}

func GetGlAggDepName(aggregatorId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_GLOBAL_AGG_PREFIX, DEPLOYMENT_PREFIX, aggregatorId)
}

func GetGlAggSvcName(aggregatorId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_GLOBAL_AGG_PREFIX, SERVICE_PREFIX, aggregatorId)
}

func GetGlAggConfigMapName(aggregatorId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_GLOBAL_AGG_PREFIX, CONFIG_MAP_PREFIX, aggregatorId)
}

func GetGlAggPVName(aggregatorId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_GLOBAL_AGG_PREFIX, PV_PREFIX, aggregatorId)
}

func GetGlAggPVCName(aggregatorId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_GLOBAL_AGG_PREFIX, PVC_PREFIX, aggregatorId)
}

func GetGlAggClusterAddress(aggregatorId string) string {
	return fmt.Sprintf("%s:%s", GetGlAggSvcName(aggregatorId), fmt.Sprint(FL_AGG_PORT))
}

func GetLocAggDepName(aggregatorId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_LOCAL_AGG_PREFIX, DEPLOYMENT_PREFIX, aggregatorId)
}

func GetLocAggSvcName(aggregatorId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_LOCAL_AGG_PREFIX, SERVICE_PREFIX, aggregatorId)
}

func GetLocAggConfigMapName(aggregatorId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_LOCAL_AGG_PREFIX, CONFIG_MAP_PREFIX, aggregatorId)
}

func GetLocAggPVName(aggregatorId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_LOCAL_AGG_PREFIX, PV_PREFIX, aggregatorId)
}

func GetLocAggPVCName(aggregatorId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_LOCAL_AGG_PREFIX, PVC_PREFIX, aggregatorId)
}

func GetLocAggClusterAddress(aggregatorId string) string {
	return fmt.Sprintf("%s:%s", GetLocAggSvcName(aggregatorId), fmt.Sprint(FL_AGG_PORT))
}

func GetClientDepName(clientId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_CLIENT_PREFIX, DEPLOYMENT_PREFIX, clientId)
}

func GetClientConfigMapName(clientId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_CLIENT_PREFIX, CONFIG_MAP_PREFIX, clientId)
}

func GetClientPVName(clientId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_CLIENT_PREFIX, PV_PREFIX, clientId)
}

func GetClientPVCName(clientId string) string {
	return fmt.Sprintf("%s-%s-%s", FL_CLIENT_PREFIX, PVC_PREFIX, clientId)
}

// Inference service resource name helpers
func GetInfSvcDepName(nodeId string) string {
	return fmt.Sprintf("%s-%s-%s", INF_SERVICE_PREFIX, DEPLOYMENT_PREFIX, nodeId)
}

func GetInfSvcConfigMapName(nodeId string) string {
	return fmt.Sprintf("%s-%s-%s", INF_SERVICE_PREFIX, CONFIG_MAP_PREFIX, nodeId)
}

func GetInfSvcSvcName(nodeId string) string {
	return fmt.Sprintf("%s-%s-%s", INF_SERVICE_PREFIX, SERVICE_PREFIX, nodeId)
}

func GetInfSvcClusterAddress(nodeId string) string {
	return fmt.Sprintf("%s:%s", GetInfSvcSvcName(nodeId), fmt.Sprint(INF_SERVICE_PORT))
}

// Inference proxy resource name helpers
func GetInfProxyDepName(nodeId string) string {
	return fmt.Sprintf("%s-%s-%s", INF_PROXY_PREFIX, DEPLOYMENT_PREFIX, nodeId)
}

func GetInfProxySvcName(nodeId string) string {
	return fmt.Sprintf("%s-%s-%s", INF_PROXY_PREFIX, SERVICE_PREFIX, nodeId)
}

func GetInfProxyClusterAddress(nodeId string) string {
	return fmt.Sprintf("%s:%s", GetInfProxySvcName(nodeId), fmt.Sprint(INF_PROXY_PORT))
}