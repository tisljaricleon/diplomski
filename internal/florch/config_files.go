package florch

import (
	"fmt"
	"os"
	"path/filepath"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/model"
)

const (
	flConfigDirectoryPath      = "../../configs/fl/"
	imageDirectoryPath         = "../../internal/images/"
	sharedTaskFileName         = "task.py"
	sharedMainFileName         = "main.py"
	sharedConfigTemplateName   = "config_template.yaml"
	sharedConfigFileName       = "config.yaml"
)

func BuildAggregatorConfigFiles(nodeType string, aggregator *model.FlAggregator) (map[string]string, error) {
	taskBytes, err := os.ReadFile(filepath.Join(flConfigDirectoryPath, "task", sharedTaskFileName))
	if err != nil {
		return nil, err
	}

	switch nodeType {
	case common.FL_TYPE_GLOBAL_AGGREGATOR:
		mainBytes, err := os.ReadFile(filepath.Join(imageDirectoryPath, "fl_global_aggregator", sharedMainFileName))
		if err != nil {
			return nil, err
		}
		configBytes, err := os.ReadFile(filepath.Join(imageDirectoryPath, "fl_global_aggregator", sharedConfigTemplateName))
		if err != nil {
			return nil, err
		}
		config := fmt.Sprintf(string(configBytes),
			common.FL_AGG_PORT,
			aggregator.Rounds,
			aggregator.MinFitClients,
			aggregator.MinEvaluateClients,
			aggregator.MinAvailableClients,
		)
		return map[string]string{
			sharedTaskFileName:   string(taskBytes),
			sharedMainFileName:   string(mainBytes),
			sharedConfigFileName: config,
		}, nil

	case common.FL_TYPE_LOCAL_AGGREGATOR:
		mainBytes, err := os.ReadFile(filepath.Join(imageDirectoryPath, "fl_local_aggregator", sharedMainFileName))
		if err != nil {
			return nil, err
		}
		configBytes, err := os.ReadFile(filepath.Join(imageDirectoryPath, "fl_local_aggregator", sharedConfigTemplateName))
		if err != nil {
			return nil, err
		}
		config := fmt.Sprintf(string(configBytes),
			aggregator.ParentAddress,
			common.FL_AGG_PORT,
			aggregator.LocalRounds,
			aggregator.MinFitClients,
			aggregator.MinEvaluateClients,
			aggregator.MinAvailableClients,
		)
		return map[string]string{
			sharedTaskFileName:   string(taskBytes),
			sharedMainFileName:   string(mainBytes),
			sharedConfigFileName: config,
		}, nil

	default:
		return nil, fmt.Errorf("Unsupported aggregator type: %s", nodeType)
	}
}

func BuildClientConfigFiles(client *model.FlClient) (map[string]string, error) {
	taskBytes, err := os.ReadFile(filepath.Join(flConfigDirectoryPath, "task", sharedTaskFileName))
	if err != nil {
		return nil, err
	}
	mainBytes, err := os.ReadFile(filepath.Join(imageDirectoryPath, "fl_client", sharedMainFileName))
	if err != nil {
		return nil, err
	}
	configBytes, err := os.ReadFile(filepath.Join(imageDirectoryPath, "fl_client", sharedConfigTemplateName))
	if err != nil {
		return nil, err
	}
	config := fmt.Sprintf(string(configBytes),
		client.ParentAddress,
		client.PartitionId,
		client.NumPartitions,
		client.Epochs,
		client.BatchSize,
		client.LearningRate,
	)
	return map[string]string{
		sharedTaskFileName:   string(taskBytes),
		sharedMainFileName:   string(mainBytes),
		sharedConfigFileName: config,
	}, nil
}

func BuildInfServiceConfigFiles(nodeType string) (map[string]string, error) {
	if !isValidNodeType(nodeType) {
		return nil, fmt.Errorf("Unsupported node type: %s", nodeType)
	}

	infServingPath := filepath.Join(imageDirectoryPath, "inf_service")
	configBytes, err := os.ReadFile(filepath.Join(infServingPath, sharedConfigTemplateName))
	if err != nil {
		return nil, err
	}
	config := fmt.Sprintf(string(configBytes), common.INF_SERVICE_PORT)

	servingBytes, err := os.ReadFile(filepath.Join(infServingPath, sharedMainFileName))
	if err != nil {
		return nil, err
	}

	return map[string]string{
		sharedMainFileName:   string(servingBytes),
		sharedConfigFileName: config,
	}, nil
}

func isValidNodeType(nodeType string) bool {
	return nodeType == common.FL_TYPE_GLOBAL_AGGREGATOR || nodeType == common.FL_TYPE_LOCAL_AGGREGATOR || nodeType == common.FL_TYPE_CLIENT
}