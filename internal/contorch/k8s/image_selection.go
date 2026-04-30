package k8sorch

import (
	"fmt"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
)

func (orch *K8sOrchestrator) getNodeImageType(nodeId string) (string, error) {
	node, exists := orch.availableNodes[nodeId]
	if !exists {
		return "", fmt.Errorf("node %s not found", nodeId)
	}

	imageType := node.Labels.Common.ImageType
	if imageType != common.IMAGE_TYPE_RPI && imageType != common.IMAGE_TYPE_JETSON {
		return "", fmt.Errorf("unsupported image type %q on node %s", imageType, nodeId)
	}

	return imageType, nil
}

func getFlImage(imageType string) (string, error) {
	switch imageType {
	case common.IMAGE_TYPE_RPI:
		return common.FL_RPI_IMAGE, nil
	case common.IMAGE_TYPE_JETSON:
		return common.FL_JETSON_IMAGE, nil
	default:
		return "", fmt.Errorf("unsupported image type: %s", imageType)
	}
}

func getInfServiceImage(imageType string) (string, error) {
	switch imageType {
	case common.IMAGE_TYPE_RPI:
		return common.INF_SERVICE_RPI_IMAGE, nil
	case common.IMAGE_TYPE_JETSON:
		return common.INF_SERVICE_JETSON_IMAGE, nil
	default:
		return "", fmt.Errorf("unsupported image type: %s", imageType)
	}
}

func getInfProxyImage(imageType string) (string, error) {
	switch imageType {
	case common.IMAGE_TYPE_RPI:
		return common.INF_PROXY_RPI_IMAGE, nil
	case common.IMAGE_TYPE_JETSON:
		return common.INF_PROXY_JETSON_IMAGE, nil
	default:
		return "", fmt.Errorf("unsupported image type: %s", imageType)
	}
}
