package k8sorch

import (
	"fmt"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/model"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func BuildAggregatorService(nodeType string, flAggregator *model.FlAggregator) *corev1.Service {
	svcName := common.GetGlAggSvcName(flAggregator.Id)
	selector := fmt.Sprintf("ga-%s", flAggregator.Id)

	if nodeType == common.FL_TYPE_LOCAL_AGGREGATOR {
		svcName = common.GetLocAggSvcName(flAggregator.Id)
		selector = fmt.Sprintf("la-%s", flAggregator.Id)
	}

	service := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{
			Name: svcName,
		},
		Spec: corev1.ServiceSpec{
			ClusterIP: "None",
			Selector: map[string]string{
				"fl": selector,
			},
			Ports: []corev1.ServicePort{
				{
					Port: flAggregator.Port,
				},
			},
		},
	}

	return service
}