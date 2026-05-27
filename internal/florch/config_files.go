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
	sharedNginxConfigFileName  = "nginx.conf"
	sharedProxyLuaFileName     = "proxy.lua"
	sharedHttpServerFileName   = "http_server.py"
)

func BuildAggregatorConfigFiles(nodeType string, aggregator *model.FlAggregator) (map[string]string, error) {
	metricsServerURL := common.GetInfProxyMetricsServerURL(aggregator.Id)
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
			aggregator.AomRoundsThreshold,
			aggregator.AomSelectionEnabled,
			metricsServerURL,
			common.FL_DATASET_DIR,
			common.FL_MODEL_FILE,
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
			aggregator.Rounds,
			aggregator.MinFitClients,
			aggregator.MinEvaluateClients,
			aggregator.MinAvailableClients,
			metricsServerURL,
			common.FL_DATASET_DIR,
			common.FL_MODEL_FILE,
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
	metricsServerURL := common.GetInfProxyMetricsServerURL(client.Id)
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
		metricsServerURL,
		common.FL_DATASET_DIR,
		common.FL_MODEL_FILE,
	)
	return map[string]string{
		sharedTaskFileName:   string(taskBytes),
		sharedMainFileName:   string(mainBytes),
		sharedConfigFileName: config,
	}, nil
}

func BuildInfServiceConfigFiles() (map[string]string, error) {
	infServingPath := filepath.Join(imageDirectoryPath, "inf_service")
	servingBytes, err := os.ReadFile(filepath.Join(infServingPath, sharedMainFileName))
	if err != nil {
		return nil, err
	}

	return map[string]string{
		sharedMainFileName:	 string(servingBytes),
	}, nil
}

func BuildInfProxyConfigFiles() (map[string]string, error) {
	infProxyPath := filepath.Join(imageDirectoryPath, "inf_proxy")
	nginxConfigBytes, err := os.ReadFile(filepath.Join(infProxyPath, sharedNginxConfigFileName))
	if err != nil {
		return nil, err
	}

	proxyLuaBytes, err := os.ReadFile(filepath.Join(infProxyPath, "lua", sharedProxyLuaFileName))
	if err != nil {
		return nil, err
	}

	httpServerBytes, err := os.ReadFile(filepath.Join(infProxyPath, sharedHttpServerFileName))
	if err != nil {
		return nil, err
	}

	return map[string]string{
		sharedNginxConfigFileName: string(nginxConfigBytes),
		sharedProxyLuaFileName:    string(proxyLuaBytes),
		sharedHttpServerFileName:  string(httpServerBytes),
	}, nil
}