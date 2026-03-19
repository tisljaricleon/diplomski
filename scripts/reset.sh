cd ~/fl_orchestrator
sudo bash scripts/cleanup.sh default
cd ~
git -C fl_orchestrator pull
mkdir -p ~/fl_orchestrator/configs/cluster
sudo cp /etc/rancher/k3s/k3s.yaml ~/fl_orchestrator/configs/cluster/kube_config.yaml
sudo chmod 644 ~/fl_orchestrator/configs/cluster/kube_config.yaml