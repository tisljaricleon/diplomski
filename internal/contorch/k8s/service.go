package k8sorch

import (
	"fmt"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/model"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func BuildGlobalAggregatorService(flAggregator *model.FlAggregator) *corev1.Service {
	service := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{
			Name: common.GetGlobalAggregatorServiceName(flAggregator.Id),
		},
		Spec: corev1.ServiceSpec{
			ClusterIP: "None",
			Selector: map[string]string{
				"fl": "ga",
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

func BuildGlobalAggregatorServingService(flAggregator *model.FlAggregator) *corev1.Service {
	service := &corev1.Service{
	       ObjectMeta: metav1.ObjectMeta{
		       Name: common.GetGlobalAggregatorServingServiceName(flAggregator.Id),
	       },
	       Spec: corev1.ServiceSpec{
		       Type: corev1.ServiceTypeNodePort,
		       Selector: map[string]string{
			       "fl": fmt.Sprintf("serving-%s", flAggregator.Id),
		       },
		       Ports: []corev1.ServicePort{
			       {
				       Port: common.GLOBAL_AGGREGATOR_SERVING_PORT,
				       TargetPort: intstrFromInt(common.GLOBAL_AGGREGATOR_SERVING_PORT),
				       NodePort: common.GLOBAL_AGGREGATOR_SERVING_NODE_PORT,
			       },
		       },
	       },
	}

	return service
}

func BuildLocalAggregatorService(flAggregator *model.FlAggregator) *corev1.Service {
	service := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{
			Name: common.GetLocalAggregatorServiceName(flAggregator.Id),
		},
		Spec: corev1.ServiceSpec{
			ClusterIP: "None",
			Selector: map[string]string{
				"fl": fmt.Sprintf("la-%s", flAggregator.Id),
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

func BuildClientServingService(flAggregator *model.FlAggregator) *corev1.Service {
	service := &corev1.Service{
	       ObjectMeta: metav1.ObjectMeta{
		       Name: common.GetClientServingServiceName(flAggregator.Id),
	       },
	       Spec: corev1.ServiceSpec{
		       Type: corev1.ServiceTypeNodePort,
		       Selector: map[string]string{
			       "fl": fmt.Sprintf("serving-%s", flAggregator.Id),
		       },
		       Ports: []corev1.ServicePort{
			       {
				       Port: common.FL_CLIENT_SERVING_PORT,
				       TargetPort: intstrFromInt(common.FL_CLIENT_SERVING_PORT),
				       NodePort: common.FL_CLIENT_SERVING_NODE_PORT,
			       },
		       },
	       },
	}

	return service
}
