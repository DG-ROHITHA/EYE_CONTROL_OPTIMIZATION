"""
Performance Comparison Tool
Compares original vs optimized eye-tracking system
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import json

class PerformanceBenchmark:
    """Benchmark tool for eye-tracking performance"""
    
    def __init__(self):
        self.metrics = {
            'original': {
                'processing_times': [],
                'fps_values': [],
                'cpu_usage': [],
                'accuracy_scores': []
            },
            'optimized': {
                'processing_times': [],
                'fps_values': [],
                'cpu_usage': [],
                'accuracy_scores': []
            }
        }
    
    def record_frame(self, system_type, processing_time, fps, cpu_usage=None, accuracy=None):
        """Record metrics for a single frame"""
        self.metrics[system_type]['processing_times'].append(processing_time)
        self.metrics[system_type]['fps_values'].append(fps)
        if cpu_usage is not None:
            self.metrics[system_type]['cpu_usage'].append(cpu_usage)
        if accuracy is not None:
            self.metrics[system_type]['accuracy_scores'].append(accuracy)
    
    def generate_report(self):
        """Generate comparison report"""
        print("\n" + "="*70)
        print("📊 PERFORMANCE COMPARISON REPORT")
        print("="*70)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        for system_type in ['original', 'optimized']:
            print(f"\n{system_type.upper()} SYSTEM:")
            print("-"*70)
            
            data = self.metrics[system_type]
            
            if data['processing_times']:
                avg_proc = np.mean(data['processing_times'])
                min_proc = np.min(data['processing_times'])
                max_proc = np.max(data['processing_times'])
                std_proc = np.std(data['processing_times'])
                
                print(f"  Processing Time:")
                print(f"    Average: {avg_proc:.2f}ms")
                print(f"    Min: {min_proc:.2f}ms")
                print(f"    Max: {max_proc:.2f}ms")
                print(f"    Std Dev: {std_proc:.2f}ms")
            
            if data['fps_values']:
                avg_fps = np.mean(data['fps_values'])
                min_fps = np.min(data['fps_values'])
                max_fps = np.max(data['fps_values'])
                
                print(f"  FPS:")
                print(f"    Average: {avg_fps:.1f}")
                print(f"    Min: {min_fps:.1f}")
                print(f"    Max: {max_fps:.1f}")
            
            if data['cpu_usage']:
                avg_cpu = np.mean(data['cpu_usage'])
                print(f"  CPU Usage:")
                print(f"    Average: {avg_cpu:.1f}%")
            
            if data['accuracy_scores']:
                avg_acc = np.mean(data['accuracy_scores'])
                print(f"  Accuracy:")
                print(f"    Average: {avg_acc:.1f}%")
        
        # Comparison
        if (self.metrics['original']['processing_times'] and 
            self.metrics['optimized']['processing_times']):
            
            print("\n" + "="*70)
            print("📈 IMPROVEMENTS:")
            print("="*70)
            
            orig_proc = np.mean(self.metrics['original']['processing_times'])
            opt_proc = np.mean(self.metrics['optimized']['processing_times'])
            proc_improvement = ((orig_proc - opt_proc) / orig_proc) * 100
            
            print(f"  Processing Time: {proc_improvement:.1f}% faster")
            
            if (self.metrics['original']['fps_values'] and 
                self.metrics['optimized']['fps_values']):
                orig_fps = np.mean(self.metrics['original']['fps_values'])
                opt_fps = np.mean(self.metrics['optimized']['fps_values'])
                fps_improvement = ((opt_fps - orig_fps) / orig_fps) * 100
                
                print(f"  FPS: {fps_improvement:.1f}% higher")
            
            if (self.metrics['original']['cpu_usage'] and 
                self.metrics['optimized']['cpu_usage']):
                orig_cpu = np.mean(self.metrics['original']['cpu_usage'])
                opt_cpu = np.mean(self.metrics['optimized']['cpu_usage'])
                cpu_reduction = ((orig_cpu - opt_cpu) / orig_cpu) * 100
                
                print(f"  CPU Usage: {cpu_reduction:.1f}% reduction")
            
            if (self.metrics['original']['accuracy_scores'] and 
                self.metrics['optimized']['accuracy_scores']):
                orig_acc = np.mean(self.metrics['original']['accuracy_scores'])
                opt_acc = np.mean(self.metrics['optimized']['accuracy_scores'])
                acc_improvement = ((opt_acc - orig_acc) / orig_acc) * 100
                
                print(f"  Accuracy: {acc_improvement:.1f}% better")
        
        print("\n" + "="*70)
    
    def plot_comparison(self):
        """Generate visualization plots"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Eye-Tracking System Performance Comparison', fontsize=16)
        
        # Processing Time
        if (self.metrics['original']['processing_times'] and 
            self.metrics['optimized']['processing_times']):
            ax = axes[0, 0]
            ax.plot(self.metrics['original']['processing_times'], 
                   label='Original', alpha=0.7)
            ax.plot(self.metrics['optimized']['processing_times'], 
                   label='Optimized', alpha=0.7)
            ax.axhline(y=50, color='r', linestyle='--', label='Target (50ms)')
            ax.set_xlabel('Frame')
            ax.set_ylabel('Processing Time (ms)')
            ax.set_title('Processing Time per Frame')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        # FPS
        if (self.metrics['original']['fps_values'] and 
            self.metrics['optimized']['fps_values']):
            ax = axes[0, 1]
            ax.plot(self.metrics['original']['fps_values'], 
                   label='Original', alpha=0.7)
            ax.plot(self.metrics['optimized']['fps_values'], 
                   label='Optimized', alpha=0.7)
            ax.axhline(y=30, color='g', linestyle='--', label='Target (30 FPS)')
            ax.set_xlabel('Frame')
            ax.set_ylabel('FPS')
            ax.set_title('Frames Per Second')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        # CPU Usage
        if (self.metrics['original']['cpu_usage'] and 
            self.metrics['optimized']['cpu_usage']):
            ax = axes[1, 0]
            ax.plot(self.metrics['original']['cpu_usage'], 
                   label='Original', alpha=0.7)
            ax.plot(self.metrics['optimized']['cpu_usage'], 
                   label='Optimized', alpha=0.7)
            ax.set_xlabel('Frame')
            ax.set_ylabel('CPU Usage (%)')
            ax.set_title('CPU Usage Over Time')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        # Comparison Bar Chart
        ax = axes[1, 1]
        metrics_names = []
        original_vals = []
        optimized_vals = []
        
        if (self.metrics['original']['processing_times'] and 
            self.metrics['optimized']['processing_times']):
            metrics_names.append('Proc Time\n(ms)')
            original_vals.append(np.mean(self.metrics['original']['processing_times']))
            optimized_vals.append(np.mean(self.metrics['optimized']['processing_times']))
        
        if (self.metrics['original']['fps_values'] and 
            self.metrics['optimized']['fps_values']):
            metrics_names.append('FPS')
            original_vals.append(np.mean(self.metrics['original']['fps_values']))
            optimized_vals.append(np.mean(self.metrics['optimized']['fps_values']))
        
        if metrics_names:
            x = np.arange(len(metrics_names))
            width = 0.35
            
            ax.bar(x - width/2, original_vals, width, label='Original', alpha=0.8)
            ax.bar(x + width/2, optimized_vals, width, label='Optimized', alpha=0.8)
            
            ax.set_ylabel('Value')
            ax.set_title('Average Performance Metrics')
            ax.set_xticks(x)
            ax.set_xticklabels(metrics_names)
            ax.legend()
            ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        # Save plot
        filename = f"performance_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"\n📊 Plot saved as: {filename}")
        
        plt.show()
    
    def export_json(self, filename='benchmark_results.json'):
        """Export results to JSON"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'metrics': {}
        }
        
        for system_type in ['original', 'optimized']:
            data = self.metrics[system_type]
            results['metrics'][system_type] = {
                'processing_time': {
                    'average': float(np.mean(data['processing_times'])) if data['processing_times'] else None,
                    'min': float(np.min(data['processing_times'])) if data['processing_times'] else None,
                    'max': float(np.max(data['processing_times'])) if data['processing_times'] else None,
                    'std': float(np.std(data['processing_times'])) if data['processing_times'] else None
                },
                'fps': {
                    'average': float(np.mean(data['fps_values'])) if data['fps_values'] else None,
                    'min': float(np.min(data['fps_values'])) if data['fps_values'] else None,
                    'max': float(np.max(data['fps_values'])) if data['fps_values'] else None
                }
            }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"📄 Results exported to: {filename}")


# Example usage simulation
if __name__ == "__main__":
    print("🔬 Eye-Tracking Performance Benchmark Tool")
    print("="*70)
    
    benchmark = PerformanceBenchmark()
    
    # Simulate original system data (worse performance)
    print("\n📊 Simulating ORIGINAL system (100 frames)...")
    for i in range(100):
        processing_time = np.random.normal(100, 20)  # Avg 100ms
        fps = 1000 / processing_time if processing_time > 0 else 0
        cpu_usage = np.random.normal(75, 10)
        
        benchmark.record_frame('original', processing_time, fps, cpu_usage)
    
    # Simulate optimized system data (better performance)
    print("📊 Simulating OPTIMIZED system (100 frames)...")
    for i in range(100):
        processing_time = np.random.normal(35, 8)  # Avg 35ms
        fps = 1000 / processing_time if processing_time > 0 else 0
        cpu_usage = np.random.normal(30, 5)
        
        benchmark.record_frame('optimized', processing_time, fps, cpu_usage)
    
    # Generate report
    benchmark.generate_report()
    
    # Export data
    benchmark.export_json()
    
    # Create visualization
    print("\n📊 Generating comparison plots...")
    try:
        benchmark.plot_comparison()
    except Exception as e:
        print(f"⚠️  Could not generate plots: {e}")
        print("   (matplotlib may not be available)")
    
    print("\n✅ Benchmark complete!")
    print("\n💡 TIP: To use with real systems:")
    print("   1. Import this class in your eye-tracking scripts")
    print("   2. Call benchmark.record_frame() after each frame")
    print("   3. Call benchmark.generate_report() when done")

"""
INTEGRATION EXAMPLE:

# In your eye-tracking script:
from performance_comparison import PerformanceBenchmark

benchmark = PerformanceBenchmark()

while True:
    start = time.time()
    
    # Your processing code here...
    
    processing_time = (time.time() - start) * 1000  # Convert to ms
    fps = perf_monitor.get_fps()
    
    benchmark.record_frame('optimized', processing_time, fps)

# When done:
benchmark.generate_report()
benchmark.export_json()
benchmark.plot_comparison()
"""
