package florch

import (
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/contorch"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/events"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/florch/cost"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/florch/flconfig"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/model"
	"github.com/hashicorp/go-hclog"
)

type FlOrchestrator struct {
	contOrch                 contorch.IContainerOrchestrator
	configurationModel       flconfig.IFlConfigurationModel
	eventBus                 *events.EventBus
	logger                   hclog.Logger
	resultsFileName          string
	nodesMap                 map[string]*model.Node
	batchSize                int32
	learningRate             float32
	globalRounds             int32
	minFitClients            int32
	minEvaluateClients       int32
	minAvailableClients      int32
	configuration            *flconfig.FlConfiguration
	modelSize                float32
	costConfiguration        *cost.CostConfiguration
	costSource               cost.CostSource
	progress                 *FlProgress
	reconfigurationEvaluator *ReconfigurationEvaluator
	rvaEnabled               bool
	enableServing            bool
}

type FlProgress struct {
	globalRound          int32
	accuracies           []float32
	losses               []float32
	accuracyHasConverged bool
	currentCost          float32
	costPerGlobalRound   float32
}

func NewFlOrchestrator(contOrch contorch.IContainerOrchestrator, eventBus *events.EventBus, logger hclog.Logger,
	configurationModelName string, epochs int32, localRounds int32, globalRounds int32, minFitClients int32, minEvaluateClients int32, minAvailableClients int32,
	batchSize int32, learningRate float32,
	modelSize float32, costSource cost.CostSource, costConfiguration *cost.CostConfiguration, rvaEnabled bool, enableServing bool) (*FlOrchestrator, error) {
	orch := &FlOrchestrator{
		contOrch:                 contOrch,
		eventBus:                 eventBus,
		logger:                   logger,
		batchSize:                batchSize,
		learningRate:             learningRate,
		globalRounds:             globalRounds,
		minFitClients:            minFitClients,
		minEvaluateClients:       minEvaluateClients,
		minAvailableClients:      minAvailableClients,
		modelSize:                modelSize,
		costConfiguration:        costConfiguration,
		costSource:               costSource,
		rvaEnabled:               rvaEnabled,
		enableServing:            enableServing,
		reconfigurationEvaluator: &ReconfigurationEvaluator{isActive: false},
	}

	switch configurationModelName {
	case flconfig.MinimizeKld_ConfigModelName:
		orch.configurationModel = flconfig.NewMinimizeKldConfiguration(epochs, localRounds, globalRounds)
	case flconfig.MinimizeCommCost_ConfigModelName:
		orch.configurationModel = flconfig.NewMinimizeCommCostGreedyConfiguration(epochs, localRounds, globalRounds, modelSize)
	case flconfig.Cent_Hier_ConfigModelName:
		orch.configurationModel = flconfig.NewCentrHierFlConfiguration(modelSize, costConfiguration.Budget)
	default:
		err := fmt.Errorf("invalid config model: %s", configurationModelName)
		return nil, err
	}

	return orch, nil
}


var rememberRemovedClientsIDS []int

func (orch *FlOrchestrator) Start() error {
	nodesMap, err := orch.contOrch.GetAvailableNodes(true)
	if err != nil {
		orch.logger.Error(err.Error())
		return err
	}
	orch.nodesMap = nodesMap

	rememberRemovedClientsIDS = []int{-1}

	// set cofiguration and deploy FL
	orch.configuration = orch.configurationModel.GetOptimalConfiguration(nodesMapToArray(orch.nodesMap))
	if orch.configuration.GlobalAggregator == nil || orch.configuration.GlobalAggregator.Id == "" {
		return fmt.Errorf("no global aggregator node found; verify node labels include %s%s=%s", common.FlPrefix, common.FlTypeLabel, common.FL_TYPE_GLOBAL_AGGREGATOR)
	}

	if len(orch.configuration.Clients) == 0 {
		return fmt.Errorf("no client nodes found; verify node labels include %s%s=%s", common.FlPrefix, common.FlTypeLabel, common.FL_TYPE_CLIENT)
	}

	if orch.costSource == cost.ENERGY {
		fmt.Printf("Minimizing Energy Budget...")
	} else if orch.costSource == cost.COMMUNICATION {
		fmt.Printf("Minimizing Communication Budget...")
	} else {
		fmt.Printf("Unknown Budget...")
	}

	orch.calculateDatasetBasedScores()
	sort.Slice(orch.configuration.Clients, func(i, j int) bool {
		return orch.configuration.Clients[i].ClientUtility.DataDistributionScore < orch.configuration.Clients[j].ClientUtility.DataDistributionScore
	})

	fmt.Printf("Cost per global round: %.2f\n", cost.GetGlobalRoundCost(orch.configuration, orch.nodesMap, orch.modelSize, orch.costSource, rememberRemovedClientsIDS))
	orch.printConfiguration()
	orch.deployFl()

	orch.progress = &FlProgress{
		globalRound: 1,
		accuracies:  []float32{},
		losses:      []float32{},
		currentCost: 0.0,
	}
	go orch.monitorFlProgress()

	nodeStateChangeChan := make(chan events.Event)
	orch.eventBus.Subscribe(common.NODE_STATE_CHANGE_EVENT_TYPE, nodeStateChangeChan)
	go orch.nodeStateChangeHandler(nodeStateChangeChan)

	//go orch.contOrch.StartNodeStateChangeNotifier()

	flFinishedChan := make(chan events.Event)
	orch.eventBus.Subscribe(common.FL_FINISHED_EVENT_TYPE, flFinishedChan)
	go orch.flFinishedHandler(flFinishedChan)

	orch.resultsFileName = getResultsFileName()

	return nil
}

func isAlreadyRemoved(x int) bool {
	for _, v := range rememberRemovedClientsIDS {
		if v == x {
			return true
		}
	}
	return false
}

func parseClientID(s string) (int, error) {
	s = strings.TrimSpace(strings.ToLower(s))
	if !strings.HasPrefix(s, "n") || len(s) == 1 {
		return 0, fmt.Errorf("bad id: %q (expected like n30)", s)
	}
	return strconv.Atoi(s[1:])
}

func (orch *FlOrchestrator) Stop() {
	orch.contOrch.StopAllNotifiers()
	orch.removeFl()
}

func (orch *FlOrchestrator) deployFl() {
	orch.deployGlAgg(orch.configuration.GlobalAggregator)
	if err := orch.deployGlAggInf(orch.configuration.GlobalAggregator); err != nil {
		orch.logger.Error(fmt.Sprintf("Error while deploying global aggregator inference: %s", err.Error()))
	}
	time.Sleep(100 * time.Second)

	for _, localAggregator := range orch.configuration.LocalAggregators {
		orch.deployLocAgg(localAggregator)
		if err := orch.deployLocAggInf(localAggregator); err != nil {
			orch.logger.Error(fmt.Sprintf("Error while deploying local aggregator inference for %s: %s", localAggregator.Id, err.Error()))
		}
		time.Sleep(1 * time.Second)
	}
	time.Sleep(60 * time.Second)

	for _, client := range orch.configuration.Clients {
		client.BatchSize = orch.batchSize
		client.LearningRate = orch.learningRate
		orch.deployClient(client)
		if err := orch.deployClientInf(client); err != nil {
			orch.logger.Error(fmt.Sprintf("Error while deploying client inference for %s: %s", client.Id, err.Error()))
		}
		time.Sleep(1 * time.Second)
	}
}

func (orch *FlOrchestrator) removeFl() {
	for _, client := range orch.configuration.Clients {
		if err := orch.removeClientInf(client); err != nil {
			orch.logger.Error(fmt.Sprintf("Error while removing client inference for %s: %s", client.Id, err.Error()))
		}
		orch.contOrch.RemoveClient(client)
	}

	for _, localAggregator := range orch.configuration.LocalAggregators {
		if err := orch.removeLocAggInf(localAggregator); err != nil {
			orch.logger.Error(fmt.Sprintf("Error while removing local aggregator inference for %s: %s", localAggregator.Id, err.Error()))
		}
		orch.contOrch.RemoveLocAgg(localAggregator)
	}

	if err := orch.removeGlAggInf(orch.configuration.GlobalAggregator); err != nil {
		orch.logger.Error(fmt.Sprintf("Error while removing global aggregator inference: %s", err.Error()))
	}
	orch.contOrch.RemoveGlAgg(orch.configuration.GlobalAggregator)
}

func (orch *FlOrchestrator) reconfigure(newConfiguration *flconfig.FlConfiguration) {
	orch.logger.Info("Starting reconfiguration:")
	orch.printConfiguration()

	oldConfiguration := orch.configuration

	for _, oldClient := range oldConfiguration.Clients {
		if orch.costSource == cost.ENERGY {
			cl_id, _ := parseClientID(oldClient.Id)
			if isAlreadyRemoved(cl_id) {
				fmt.Printf("Client already removed from a cluster: n%s", oldClient.Id)
				continue
			}
		}
		newClient := common.GetClientInArray(newConfiguration.Clients, oldClient.Id)
		if (newClient == &model.FlClient{}) {
			if err := orch.removeClientInf(oldClient); err != nil {
				orch.logger.Error(fmt.Sprintf("Error while removing client inference for %s: %s", oldClient.Id, err.Error()))
			}
			orch.contOrch.RemoveClient(oldClient)
			orch.logger.Info(fmt.Sprintf("Removed client: %s", oldClient.Id))
		} else if oldClient.ParentNodeId != newClient.ParentNodeId {
			if err := orch.removeClientInf(oldClient); err != nil {
				orch.logger.Error(fmt.Sprintf("Error while removing client inference for %s: %s", oldClient.Id, err.Error()))
			}
			orch.contOrch.RemoveClient(oldClient)
			orch.logger.Info(fmt.Sprintf("Client changing cluster: %s", oldClient.Id))
		}
	}

	time.Sleep(90 * time.Second)
	orch.logger.Info("Deploying new configuration...")

	for _, newClient := range newConfiguration.Clients {
		if orch.costSource == cost.ENERGY {
			cl_id, _ := parseClientID(newClient.Id)
			if isAlreadyRemoved(cl_id) {
				fmt.Printf("Client already removed from a cluster: n%s", newClient.Id)
				continue
			}
		}
		newClient.BatchSize = orch.batchSize
		newClient.LearningRate = orch.learningRate
		oldClient := common.GetClientInArray(oldConfiguration.Clients, newClient.Id)
		if (oldClient == &model.FlClient{}) {
			if err := orch.deployClient(newClient); err != nil {
				orch.logger.Error(fmt.Sprintf("Error while deploying client %s: %s", newClient.Id, err.Error()))
				continue
			}
			if err := orch.deployClientInf(newClient); err != nil {
				orch.logger.Error(fmt.Sprintf("Error while deploying client inference for %s: %s", newClient.Id, err.Error()))
			}
		} else if oldClient.ParentAddress != newClient.ParentAddress {
			if err := orch.deployClient(newClient); err != nil {
				orch.logger.Error(fmt.Sprintf("Error while deploying client %s: %s", newClient.Id, err.Error()))
				continue
			}
			if err := orch.deployClientInf(newClient); err != nil {
				orch.logger.Error(fmt.Sprintf("Error while deploying client inference for %s: %s", newClient.Id, err.Error()))
			}
		}
	}

	orch.configuration = newConfiguration
}