kubectl label --overwrite nodes rpi4-5 fl/type=global_aggregator

kubectl label --overwrite nodes orinnano-2 fl/type=client
kubectl label --overwrite nodes orinnano-3 fl/type=client
kubectl label --overwrite nodes orinnano-4 fl/type=client

kubectl label --overwrite nodes orinnano-2 comm/rpi4-5=100 fl/num-partitions=3 fl/partition-id=0
kubectl label --overwrite nodes orinnano-3 comm/rpi4-5=100 fl/num-partitions=3 fl/partition-id=1
kubectl label --overwrite nodes orinnano-4 comm/rpi4-5=100 fl/num-partitions=3 fl/partition-id=2