package contorch

import (
	"bytes"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/model"
)

type IContainerOrchestrator interface {
	GetAvailableNodes(initialRequest bool) (map[string]*model.Node, error)
	StartNodeStateChangeNotifier()
	StopAllNotifiers()

	CreateGlAgg(aggregator *model.FlAggregator, configFiles map[string]string) error
	RemoveGlAgg(aggregator *model.FlAggregator) error
	CreateLocAgg(aggregator *model.FlAggregator, configFiles map[string]string) error
	RemoveLocAgg(aggregator *model.FlAggregator) error
	CreateClient(client *model.FlClient, configFiles map[string]string) error
	RemoveClient(client *model.FlClient) error

	GetLocAggLogs(aggregatorId string) (bytes.Buffer, error)
	GetGlAggLogs(aggregatorId string) (bytes.Buffer, error)
	GetClientLogs(clientId string) (bytes.Buffer, error)

	CreateInfService(nodeType string, nodeId string, configFiles map[string]string) error
	RemoveInfService(nodeId string) error

	CreateInfProxy(nodeId string, configFiles map[string]string, parentServiceURL string) error
	RemoveInfProxy(nodeId string) error
}
