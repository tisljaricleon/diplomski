kubectl label --overwrite nodes rpi4-5 fl/type=global_aggregator inf-proxy/node-port=30480 common/image-type=rpi common/use-mps=false

kubectl label --overwrite nodes orinnano-2 fl/type=client common/image-type=jetson common/use-mps=true
kubectl label --overwrite nodes orinnano-3 fl/type=client common/image-type=jetson common/use-mps=true
kubectl label --overwrite nodes orinnano-4 fl/type=client common/image-type=jetson common/use-mps=true

kubectl label --overwrite nodes orinnano-2 comm/rpi4-5=100 fl/num-partitions=3 fl/partition-id=0 inf-proxy/node-port=30380
kubectl label --overwrite nodes orinnano-3 comm/rpi4-5=100 fl/num-partitions=3 fl/partition-id=1 inf-proxy/node-port=30381
kubectl label --overwrite nodes orinnano-4 comm/rpi4-5=100 fl/num-partitions=3 fl/partition-id=2 inf-proxy/node-port=30382