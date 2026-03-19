package k8sorch

import (
	"fmt"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/api/resource"
)

func BuildGlobalAggregatorPVC(id string, namespace string) *corev1.PersistentVolumeClaim {
       return &corev1.PersistentVolumeClaim{
	       ObjectMeta: metav1.ObjectMeta{
		       Name:      common.GetGlobalAggregatorPVCName(id),
		       Namespace: namespace,
	       },
	       Spec: corev1.PersistentVolumeClaimSpec{
		       AccessModes: []corev1.PersistentVolumeAccessMode{
			       corev1.ReadWriteOnce,
		       },
		       Resources: corev1.ResourceRequirements{
			       Requests: corev1.ResourceList{
				       corev1.ResourceStorage: resource.MustParse("250Mi"),
			       },
		       },
		       StorageClassName: pointerToEmptyString(),
	       },
       }
}

func BuildLocalAggregatorPVC(id string, namespace string) *corev1.PersistentVolumeClaim {
       return &corev1.PersistentVolumeClaim{
	       ObjectMeta: metav1.ObjectMeta{
		       Name:      common.GetLocalAggregatorPVCName(id),
		       Namespace: namespace,
	       },
	       Spec: corev1.PersistentVolumeClaimSpec{
		       AccessModes: []corev1.PersistentVolumeAccessMode{
			       corev1.ReadWriteOnce,
		       },
		       Resources: corev1.ResourceRequirements{
			       Requests: corev1.ResourceList{
				       corev1.ResourceStorage: resource.MustParse("250Mi"),
			       },
		       },
		       StorageClassName: pointerToEmptyString(),
	       },
       }
}

func BuildClientPVC(id string, namespace string) *corev1.PersistentVolumeClaim {
       return &corev1.PersistentVolumeClaim{
	       ObjectMeta: metav1.ObjectMeta{
		       Name:      common.GetClientPVCName(id),
		       Namespace: namespace,
	       },
	       Spec: corev1.PersistentVolumeClaimSpec{
		       AccessModes: []corev1.PersistentVolumeAccessMode{
			       corev1.ReadWriteOnce,
		       },
		       Resources: corev1.ResourceRequirements{
			       Requests: corev1.ResourceList{
				       corev1.ResourceStorage: resource.MustParse("250Mi"),
			       },
		       },
		       StorageClassName: pointerToEmptyString(),
	       },
       }
}

func pointerToEmptyString() *string {
	s := ""
	return &s
}


