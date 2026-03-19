package k8sorch

import (
	"fmt"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/api/resource"
)

func BuildGlobalAggregatorPV(id string, namespace string) *corev1.PersistentVolume {
       return &corev1.PersistentVolume{
	       ObjectMeta: metav1.ObjectMeta{
		       Name: common.GetGlobalAggregatorPersistentVolumeName(id),
	       },
	       Spec: corev1.PersistentVolumeSpec{
		       Capacity: corev1.ResourceList{
			       corev1.ResourceStorage: resource.MustParse("250Mi"),
		       },
		       AccessModes: []corev1.PersistentVolumeAccessMode{
			       corev1.ReadWriteOnce,
		       },
		       PersistentVolumeReclaimPolicy: corev1.PersistentVolumeReclaimRetain,
		       HostPath: &corev1.HostPathVolumeSource{
			       Path: fmt.Sprintf("%s/global", common.PERSISTENT_VOLUME_PATH),
		       },
		       ClaimRef: &corev1.ObjectReference{
			       Kind:      "PersistentVolumeClaim",
			       Namespace:  namespace,
			       Name:      common.GetGlobalAggregatorPVCName(id),
		       },
	       },
       }
}

func BuildLocalAggregatorPV(id string, namespace string) *corev1.PersistentVolume {
       return &corev1.PersistentVolume{
	       ObjectMeta: metav1.ObjectMeta{
		       Name: common.GetLocalAggregatorPersistentVolumeName(id),
	       },
	       Spec: corev1.PersistentVolumeSpec{
		       Capacity: corev1.ResourceList{
			       corev1.ResourceStorage: resource.MustParse("250Mi"),
		       },
		       AccessModes: []corev1.PersistentVolumeAccessMode{
			       corev1.ReadWriteOnce,
		       },
		       PersistentVolumeReclaimPolicy: corev1.PersistentVolumeReclaimRetain,
		       HostPath: &corev1.HostPathVolumeSource{
			       Path: fmt.Sprintf("%s/local-%s", common.PERSISTENT_VOLUME_PATH, id),
		       },
		       ClaimRef: &corev1.ObjectReference{
			       Kind:      "PersistentVolumeClaim",
			       Namespace:  namespace,
			       Name:      common.GetLocalAggregatorPVCName(id),
		       },
	       },
       }
}

func BuildClientPV(id string, namespace string) *corev1.PersistentVolume {
       return &corev1.PersistentVolume{
	       ObjectMeta: metav1.ObjectMeta{
		       Name: common.GetClientPersistentVolumeName(id),
	       },
	       Spec: corev1.PersistentVolumeSpec{
		       Capacity: corev1.ResourceList{
			       corev1.ResourceStorage: resource.MustParse("250Mi"),
		       },
		       AccessModes: []corev1.PersistentVolumeAccessMode{
			       corev1.ReadWriteOnce,
		       },
		       PersistentVolumeReclaimPolicy: corev1.PersistentVolumeReclaimRetain,
		       HostPath: &corev1.HostPathVolumeSource{
			       Path: fmt.Sprintf("%s/client-%s", common.PERSISTENT_VOLUME_PATH, id),
		       },
		       ClaimRef: &corev1.ObjectReference{
			       Kind:      "PersistentVolumeClaim",
			       Namespace:  namespace,
			       Name:      common.GetClientPVCName(id),
		       },
	       },
       }
}