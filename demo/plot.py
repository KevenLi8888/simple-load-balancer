import matplotlib.pyplot as plt
import numpy as np

# Data
concurrent_requests = [50, 100, 250]
round_robin = [3.12, 5.11, 9.30]
weighted_round_robin = [2.52, 4.52, 6.91]
ip_hash = [6.71, 12.32, 18.47]

# Create the plot
plt.figure(figsize=(10, 6), facecolor='#f5f5f5')  # Light gray background for the figure

# Plot each line with markers
plt.plot(concurrent_requests, round_robin, marker='o', linewidth=2, label='Round Robin')
plt.plot(concurrent_requests, weighted_round_robin, marker='s', linewidth=2, label='Weighted Round Robin')
plt.plot(concurrent_requests, ip_hash, marker='^', linewidth=2, label='IP Hash')

# Add labels and title
plt.xlabel('Number of Concurrent Requests')
plt.ylabel('Average Response Time (seconds)')
plt.title('Load Balancing Algorithm Performance Comparison')

# Add grid
plt.grid(True, linestyle='--', alpha=0.7)

# Set x-axis ticks to match our data points
plt.xticks(concurrent_requests)

# Add legend
plt.legend()

# Set light background color for the plot area (the area inside the axes)
ax = plt.gca()
ax.set_facecolor('#e6f2ff')  # 设置为淡蓝色背景

# Show the plot
plt.tight_layout()
plt.savefig('load_balancing_comparison.png')
plt.show()
