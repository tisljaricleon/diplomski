package florch

import (
	"fmt"
	"strings"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/model"
)


func (orch *FlOrchestrator) deployInfStack(nodeType string, nodeId string, parentNodeId string) error {
	serviceConfigFiles, err := BuildInfServiceConfigFiles()
	if err != nil {
		return err
	}

	if err := orch.contOrch.CreateInfService(nodeType, nodeId, serviceConfigFiles); err != nil {
		return err
	}

	proxyConfigFiles, err := BuildInfProxyConfigFiles()
	if err != nil {
		return err
	}

	parentServiceURL := ""
	if parentNodeId != "" {
		parentServiceURL = fmt.Sprintf("http://%s", common.GetInfSvcClusterAddress(parentNodeId))
	}

	if err := orch.contOrch.CreateInfProxy(nodeId, proxyConfigFiles, parentServiceURL); err != nil {
		_ = orch.contOrch.RemoveInfService(nodeId)
		return err
	}

	return nil
}

func (orch *FlOrchestrator) removeInfStack(nodeId string) error {
	errs := []string{}
	if err := orch.contOrch.RemoveInfProxy(nodeId); err != nil {
		errs = append(errs, err.Error())
	}
	if err := orch.contOrch.RemoveInfService(nodeId); err != nil {
		errs = append(errs, err.Error())
	}
	if len(errs) > 0 {
		return fmt.Errorf(strings.Join(errs, "; "))
	}

	return nil
}

func (orch *FlOrchestrator) deployGlAggInf(aggregator *model.FlAggregator) error {
	if !orch.enableServing {
		orch.logger.Info(fmt.Sprintf("Serving is disabled in FL-only mode for global aggregator %s", aggregator.Id))
		return nil
	}

	return orch.deployInfStack(common.FL_TYPE_GLOBAL_AGGREGATOR, aggregator.Id, "")
}

func (orch *FlOrchestrator) deployLocAggInf(aggregator *model.FlAggregator) error {
	if !orch.enableServing {
		orch.logger.Info(fmt.Sprintf("Serving is disabled in FL-only mode for local aggregator %s", aggregator.Id))
		return nil
	}

	parentNodeId := ""
	if orch.configuration != nil && orch.configuration.GlobalAggregator != nil {
		parentNodeId = orch.configuration.GlobalAggregator.Id
	}

	return orch.deployInfStack(common.FL_TYPE_LOCAL_AGGREGATOR, aggregator.Id, parentNodeId)
}

func (orch *FlOrchestrator) deployClientInf(client *model.FlClient) error {
	if !orch.enableServing {
		orch.logger.Info(fmt.Sprintf("Serving is disabled in FL-only mode for client %s", client.Id))
		return nil
	}

	return orch.deployInfStack(common.FL_TYPE_CLIENT, client.Id, client.ParentNodeId)
}

func (orch *FlOrchestrator) removeGlAggInf(aggregator *model.FlAggregator) error {
	if !orch.enableServing {
		return nil
	}

	return orch.removeInfStack(aggregator.Id)
}

func (orch *FlOrchestrator) removeLocAggInf(aggregator *model.FlAggregator) error {
	if !orch.enableServing {
		return nil
	}

	return orch.removeInfStack(aggregator.Id)
}

func (orch *FlOrchestrator) removeClientInf(client *model.FlClient) error {
	if !orch.enableServing {
		return nil
	}

	return orch.removeInfStack(client.Id)
}
