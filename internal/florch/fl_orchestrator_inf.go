package florch

import (
	"fmt"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/model"
)

// Inference/proxy orchestration hooks are intentionally isolated in this file.
// FL-only mode currently keeps these paths disabled.

func (orch *FlOrchestrator) deployGlAggInf(aggregator *model.FlAggregator) error {
	if !orch.enableServing {
		orch.logger.Info(fmt.Sprintf("Serving is disabled in FL-only mode for global aggregator %s", aggregator.Id))
		return nil
	}

	configFiles, err := BuildInfServiceConfigFiles(common.FL_TYPE_GLOBAL_AGGREGATOR)
	if err != nil {
		return err
	}

	return orch.contOrch.CreateInfService(common.FL_TYPE_GLOBAL_AGGREGATOR, aggregator.Id, configFiles)
}

func (orch *FlOrchestrator) deployLocAggInf(aggregator *model.FlAggregator) error {
	if !orch.enableServing {
		orch.logger.Info(fmt.Sprintf("Serving is disabled in FL-only mode for local aggregator %s", aggregator.Id))
		return nil
	}

	configFiles, err := BuildInfServiceConfigFiles(common.FL_TYPE_LOCAL_AGGREGATOR)
	if err != nil {
		return err
	}

	return orch.contOrch.CreateInfService(common.FL_TYPE_LOCAL_AGGREGATOR, aggregator.Id, configFiles)
}

func (orch *FlOrchestrator) deployClientInf(client *model.FlClient) error {
	if !orch.enableServing {
		orch.logger.Info(fmt.Sprintf("Serving is disabled in FL-only mode for client %s", client.Id))
		return nil
	}

	configFiles, err := BuildInfServiceConfigFiles(common.FL_TYPE_CLIENT)
	if err != nil {
		return err
	}

	return orch.contOrch.CreateInfService(common.FL_TYPE_CLIENT, client.Id, configFiles)
}

func (orch *FlOrchestrator) removeGlAggInf(aggregator *model.FlAggregator) error {
	if !orch.enableServing {
		return nil
	}

	return orch.contOrch.RemoveInfService(aggregator.Id)
}

func (orch *FlOrchestrator) removeLocAggInf(aggregator *model.FlAggregator) error {
	if !orch.enableServing {
		return nil
	}

	return orch.contOrch.RemoveInfService(aggregator.Id)
}

func (orch *FlOrchestrator) removeClientInf(client *model.FlClient) error {
	if !orch.enableServing {
		return nil
	}

	return orch.contOrch.RemoveInfService(client.Id)
}
