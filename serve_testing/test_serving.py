#!/usr/bin/env python
"""
Test script to send simultaneous requests to multiple client servers and monitor latency, CPU, memory, and GPU usage.
"""
import requests
import threading
import time
import argparse
import psutil
import subprocess
import os
from queue import Queue

try:
    import pynvml
    pynvml.nvmlInit()
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False


def send_request(url, image_path, latency_queue):
    start = time.time()
    with open(image_path, 'rb') as f:
        files = {'file': f}
        try:
            r = requests.post(url, files=files)
            latency = time.time() - start
            latency_queue.put(latency)
        except Exception as e:
            latency_queue.put(None)


def monitor_resources(pid, interval, duration, resource_log):
    process = psutil.Process(pid)
    start_time = time.time()
    while time.time() - start_time < duration:
        cpu = process.cpu_percent(interval=0.1)
        mem = process.memory_info().rss / (1024 * 1024)  # MB
        gpu = None
        if NVML_AVAILABLE:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                gpu = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
            except Exception:
                gpu = None
        resource_log.append((time.time() - start_time, cpu, mem, gpu))
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Test model serving with resource monitoring.")
    parser.add_argument('--clients', nargs='+', required=True, help='List of client URLs, e.g. http://localhost:8000/predict')
    parser.add_argument('--image', required=True, help='Path to test image file')
    parser.add_argument('-n', type=int, default=10, help='Number of requests per client')
    parser.add_argument('--interval', type=float, default=0.5, help='Resource monitoring interval (s)')
    parser.add_argument('--duration', type=float, default=10, help='Resource monitoring duration (s)')
    parser.add_argument('--pid', type=int, required=True, help='PID of the client server process to monitor')
    args = parser.parse_args()

    latency_queues = [Queue() for _ in args.clients]
    resource_log = []

    # Start resource monitoring thread
    monitor_thread = threading.Thread(target=monitor_resources, args=(args.pid, args.interval, args.duration, resource_log))
    monitor_thread.start()

    # Start sending requests
    threads = []
    for idx, client_url in enumerate(args.clients):
        for _ in range(args.n):
            t = threading.Thread(target=send_request, args=(client_url, args.image, latency_queues[idx]))
            t.start()
            threads.append(t)

    for t in threads:
        t.join()
    monitor_thread.join()

    # Collect and print results
    for idx, client_url in enumerate(args.clients):
        latencies = []
        while not latency_queues[idx].empty():
            latency = latency_queues[idx].get()
            if latency is not None:
                latencies.append(latency)
        if latencies:
            print(f"Client {client_url}: avg latency={sum(latencies)/len(latencies):.3f}s, min={min(latencies):.3f}s, max={max(latencies):.3f}s")
        else:
            print(f"Client {client_url}: No successful responses.")

    # Print resource usage log
    print("\nTime(s),CPU(%),Memory(MB),GPU(%)")
    for entry in resource_log:
        print(','.join(str(x) if x is not None else '' for x in entry))

if __name__ == "__main__":
    main()
