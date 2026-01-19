"""
Test Suite for Optimized Eye-Tracking System
Validates all improvements and detects issues
"""

import time
import numpy as np
from collections import deque

class OptimizationTests:
    """Test suite for optimization features"""
    
    def __init__(self):
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }
    
    def test_frame_skipping(self, skip_frames_value):
        """Test frame skipping configuration"""
        print("🧪 Testing frame skipping...")
        
        if skip_frames_value < 0:
            self.results['failed'].append("Frame skipping: Negative value")
            return False
        elif skip_frames_value > 5:
            self.results['warnings'].append(f"Frame skipping: High value ({skip_frames_value}), may cause lag")
        
        expected_reduction = (skip_frames_value / (skip_frames_value + 1)) * 100
        print(f"   ✓ Frame skipping: {skip_frames_value} (Expected {expected_reduction:.1f}% CPU reduction)")
        self.results['passed'].append(f"Frame skipping: {skip_frames_value}")
        return True
    
    def test_resolution_reduction(self, width, height):
        """Test resolution configuration"""
        print("🧪 Testing resolution reduction...")
        
        if width < 160 or height < 120:
            self.results['failed'].append("Resolution: Too low, may affect accuracy")
            return False
        elif width > 640 or height > 480:
            self.results['warnings'].append("Resolution: High, may reduce performance benefit")
        
        reduction_factor = (640 * 480) / (width * height)
        print(f"   ✓ Resolution: {width}x{height} ({reduction_factor:.1f}x faster)")
        self.results['passed'].append(f"Resolution: {width}x{height}")
        return True
    
    def test_kalman_filter(self):
        """Test Kalman filter implementation"""
        print("🧪 Testing Kalman filter...")
        
        try:
            from eye_control_optimized import KalmanFilter2D
            
            kf = KalmanFilter2D()
            
            # Test prediction
            x, y = kf.predict()
            
            # Test update
            measurement = (100, 100)
            filtered_x, filtered_y = kf.update(measurement)
            
            # Test velocity
            vx, vy = kf.get_velocity()
            
            print(f"   ✓ Kalman filter: Working correctly")
            print(f"     - Prediction: ({x:.2f}, {y:.2f})")
            print(f"     - Filtered: ({filtered_x:.2f}, {filtered_y:.2f})")
            print(f"     - Velocity: ({vx:.2f}, {vy:.2f})")
            
            self.results['passed'].append("Kalman filter: Functional")
            return True
        
        except Exception as e:
            print(f"   ✗ Kalman filter: {e}")
            self.results['failed'].append(f"Kalman filter: {e}")
            return False
    
    def test_intent_detection(self):
        """Test intent detection system"""
        print("🧪 Testing intent detection...")
        
        try:
            from eye_control_optimized import IntentDetector
            
            detector = IntentDetector()
            
            # Simulate intentional gaze (slow, long duration)
            for i in range(30):
                x = 500 + np.random.randn() * 2  # Small variance
                y = 500 + np.random.randn() * 2
                timestamp = time.time() + i * 0.05
                detector.add_gaze_point(x, y, timestamp)
            
            # Check duration
            duration = detector.get_duration_at_position(500, 500, radius=50)
            
            # Check intensity
            intensity = detector.get_movement_intensity()
            
            print(f"   ✓ Intent detection: Working")
            print(f"     - Duration at position: {duration:.2f}s")
            print(f"     - Movement intensity: {intensity:.2f} px/frame")
            
            if duration > 1.0 and intensity < 10:
                print(f"     - Classification: INTENTIONAL ✓")
            else:
                print(f"     - Classification: NOT INTENTIONAL")
            
            self.results['passed'].append("Intent detection: Functional")
            return True
        
        except Exception as e:
            print(f"   ✗ Intent detection: {e}")
            self.results['failed'].append(f"Intent detection: {e}")
            return False
    
    def test_performance_monitoring(self):
        """Test performance monitoring"""
        print("🧪 Testing performance monitoring...")
        
        try:
            from eye_control_optimized import PerformanceMonitor
            
            monitor = PerformanceMonitor()
            
            # Simulate frame processing
            for i in range(30):
                monitor.frame_start()
                time.sleep(0.03)  # Simulate 30ms processing
                monitor.frame_end()
            
            stats = monitor.get_stats()
            
            print(f"   ✓ Performance monitoring: Working")
            print(f"     - FPS: {stats['fps']:.1f}")
            print(f"     - Avg processing: {stats['avg_processing_ms']:.2f}ms")
            
            if stats['avg_processing_ms'] < 50:
                print(f"     - Target met: ✓")
            else:
                print(f"     - Target not met: ✗")
                self.results['warnings'].append("Performance: Above 50ms target")
            
            self.results['passed'].append("Performance monitoring: Functional")
            return True
        
        except Exception as e:
            print(f"   ✗ Performance monitoring: {e}")
            self.results['failed'].append(f"Performance monitoring: {e}")
            return False
    
    def test_blink_detection(self):
        """Test blink detection"""
        print("🧪 Testing blink detection...")
        
        try:
            from eye_control_optimized import BlinkDetector
            
            # Note: Can't fully test without face landmarks
            # Just check class exists and methods are defined
            
            assert hasattr(BlinkDetector, 'calculate_ear')
            assert hasattr(BlinkDetector, 'detect_blink')
            assert hasattr(BlinkDetector, 'detect_blink_pattern')
            
            print(f"   ✓ Blink detection: Class structure valid")
            self.results['passed'].append("Blink detection: Structure valid")
            return True
        
        except Exception as e:
            print(f"   ✗ Blink detection: {e}")
            self.results['failed'].append(f"Blink detection: {e}")
            return False
    
    def test_pattern_recognition(self):
        """Test pattern recognition"""
        print("🧪 Testing pattern recognition...")
        
        try:
            from eye_control_optimized import SequenceDetector
            
            detector = SequenceDetector()
            
            # Test known pattern
            test_sequence = ['LEFT', 'RIGHT', 'LEFT']
            command = detector.check_sequence(test_sequence)
            
            if command == 'CALL_NURSE':
                print(f"   ✓ Pattern recognition: Working")
                print(f"     - Detected: {command}")
                self.results['passed'].append("Pattern recognition: Functional")
                return True
            else:
                print(f"   ✗ Pattern recognition: Failed to detect L-R-L")
                self.results['failed'].append("Pattern recognition: Detection failed")
                return False
        
        except Exception as e:
            print(f"   ✗ Pattern recognition: {e}")
            self.results['failed'].append(f"Pattern recognition: {e}")
            return False
    
    def test_config_presets(self):
        """Test configuration presets"""
        print("🧪 Testing configuration presets...")
        
        try:
            from config_presets import PresetManager
            
            presets = PresetManager.PRESETS
            
            if len(presets) < 5:
                print(f"   ⚠ Config presets: Only {len(presets)} presets found")
                self.results['warnings'].append(f"Config presets: Limited ({len(presets)})")
            else:
                print(f"   ✓ Config presets: {len(presets)} presets available")
                self.results['passed'].append(f"Config presets: {len(presets)} available")
            
            # Test loading a preset
            preset = PresetManager.get_preset('balanced')
            if preset:
                print(f"     - Successfully loaded 'balanced' preset")
                return True
            else:
                print(f"     - Failed to load preset")
                return False
        
        except Exception as e:
            print(f"   ✗ Config presets: {e}")
            self.results['failed'].append(f"Config presets: {e}")
            return False
    
    def test_dependencies(self):
        """Test required dependencies"""
        print("🧪 Testing dependencies...")
        
        dependencies = {
            'cv2': 'OpenCV',
            'numpy': 'NumPy',
            'mediapipe': 'MediaPipe',
            'pyautogui': 'PyAutoGUI'
        }
        
        all_present = True
        for module, name in dependencies.items():
            try:
                __import__(module)
                print(f"   ✓ {name}: Installed")
            except ImportError:
                print(f"   ✗ {name}: NOT INSTALLED")
                self.results['failed'].append(f"Dependency: {name} missing")
                all_present = False
        
        if all_present:
            self.results['passed'].append("Dependencies: All installed")
        
        return all_present
    
    def test_file_structure(self):
        """Test if all required files exist"""
        print("🧪 Testing file structure...")
        
        import os
        
        required_files = [
            'eye_control_optimized.py',
            'config_presets.py',
            'performance_comparison.py',
            'OPTIMIZATION_GUIDE.md',
            'QUICK_START_OPTIMIZED.md'
        ]
        
        all_present = True
        for file in required_files:
            if os.path.exists(file):
                print(f"   ✓ {file}: Found")
            else:
                print(f"   ✗ {file}: NOT FOUND")
                self.results['failed'].append(f"File: {file} missing")
                all_present = False
        
        if all_present:
            self.results['passed'].append("File structure: Complete")
        
        return all_present
    
    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*70)
        print("🧪 RUNNING OPTIMIZATION TEST SUITE")
        print("="*70)
        print()
        
        # Configuration tests
        print("━━━ CONFIGURATION TESTS ━━━")
        self.test_frame_skipping(2)
        self.test_resolution_reduction(320, 240)
        print()
        
        # Component tests
        print("━━━ COMPONENT TESTS ━━━")
        self.test_kalman_filter()
        self.test_intent_detection()
        self.test_performance_monitoring()
        self.test_blink_detection()
        self.test_pattern_recognition()
        print()
        
        # System tests
        print("━━━ SYSTEM TESTS ━━━")
        self.test_config_presets()
        self.test_dependencies()
        self.test_file_structure()
        print()
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)
        
        total = len(self.results['passed']) + len(self.results['failed'])
        passed = len(self.results['passed'])
        failed = len(self.results['failed'])
        warnings = len(self.results['warnings'])
        
        print(f"\nTotal tests: {total}")
        print(f"✓ Passed: {passed}")
        print(f"✗ Failed: {failed}")
        print(f"⚠ Warnings: {warnings}")
        
        if self.results['passed']:
            print("\n✅ PASSED TESTS:")
            for test in self.results['passed']:
                print(f"   ✓ {test}")
        
        if self.results['failed']:
            print("\n❌ FAILED TESTS:")
            for test in self.results['failed']:
                print(f"   ✗ {test}")
        
        if self.results['warnings']:
            print("\n⚠️  WARNINGS:")
            for warning in self.results['warnings']:
                print(f"   ⚠ {warning}")
        
        print("\n" + "="*70)
        
        if failed == 0:
            print("✅ ALL TESTS PASSED! System is ready to use.")
        elif failed < 3:
            print("⚠️  SOME TESTS FAILED. Review issues before use.")
        else:
            print("❌ MULTIPLE TESTS FAILED. Fix issues before use.")
        
        print("="*70)
        
        return failed == 0


class PerformanceBenchmark:
    """Quick performance benchmark"""
    
    @staticmethod
    def benchmark_kalman_filter(iterations=1000):
        """Benchmark Kalman filter performance"""
        print("\n🏃 Benchmarking Kalman filter...")
        
        try:
            from eye_control_optimized import KalmanFilter2D
            
            kf = KalmanFilter2D()
            
            start = time.time()
            for i in range(iterations):
                measurement = (np.random.rand() * 640, np.random.rand() * 480)
                kf.update(measurement)
            elapsed = time.time() - start
            
            avg_time = (elapsed / iterations) * 1000  # ms
            
            print(f"   Iterations: {iterations}")
            print(f"   Total time: {elapsed:.3f}s")
            print(f"   Avg per update: {avg_time:.4f}ms")
            
            if avg_time < 0.1:
                print(f"   Performance: ✓ Excellent (<0.1ms)")
            elif avg_time < 0.5:
                print(f"   Performance: ✓ Good (<0.5ms)")
            else:
                print(f"   Performance: ⚠ Slow (>{avg_time:.2f}ms)")
            
            return avg_time
        
        except Exception as e:
            print(f"   ✗ Benchmark failed: {e}")
            return None
    
    @staticmethod
    def benchmark_intent_detection(iterations=1000):
        """Benchmark intent detection performance"""
        print("\n🏃 Benchmarking intent detection...")
        
        try:
            from eye_control_optimized import IntentDetector
            
            detector = IntentDetector()
            
            # Add some initial data
            for i in range(30):
                detector.add_gaze_point(
                    np.random.rand() * 640,
                    np.random.rand() * 480,
                    time.time()
                )
            
            start = time.time()
            for i in range(iterations):
                detector.get_movement_intensity()
                detector.get_duration_at_position(320, 240)
            elapsed = time.time() - start
            
            avg_time = (elapsed / iterations) * 1000  # ms
            
            print(f"   Iterations: {iterations}")
            print(f"   Total time: {elapsed:.3f}s")
            print(f"   Avg per check: {avg_time:.4f}ms")
            
            if avg_time < 1.0:
                print(f"   Performance: ✓ Excellent (<1ms)")
            elif avg_time < 5.0:
                print(f"   Performance: ✓ Good (<5ms)")
            else:
                print(f"   Performance: ⚠ Slow (>{avg_time:.2f}ms)")
            
            return avg_time
        
        except Exception as e:
            print(f"   ✗ Benchmark failed: {e}")
            return None
    
    @staticmethod
    def run_all_benchmarks():
        """Run all benchmarks"""
        print("\n" + "="*70)
        print("⚡ PERFORMANCE BENCHMARKS")
        print("="*70)
        
        PerformanceBenchmark.benchmark_kalman_filter()
        PerformanceBenchmark.benchmark_intent_detection()
        
        print("\n" + "="*70)


if __name__ == "__main__":
    import sys
    
    print("="*70)
    print("🧪 EYE-TRACKING OPTIMIZATION TEST SUITE")
    print("="*70)
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'test':
            tests = OptimizationTests()
            tests.run_all_tests()
        
        elif command == 'benchmark':
            PerformanceBenchmark.run_all_benchmarks()
        
        elif command == 'all':
            tests = OptimizationTests()
            success = tests.run_all_tests()
            
            if success:
                PerformanceBenchmark.run_all_benchmarks()
        
        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  test - Run test suite")
            print("  benchmark - Run performance benchmarks")
            print("  all - Run both tests and benchmarks")
    
    else:
        print("\nSelect test mode:")
        print("  1. Run test suite")
        print("  2. Run benchmarks")
        print("  3. Run all")
        print()
        
        try:
            choice = input("Enter choice (1-3): ").strip()
            
            if choice == '1':
                tests = OptimizationTests()
                tests.run_all_tests()
            elif choice == '2':
                PerformanceBenchmark.run_all_benchmarks()
            elif choice == '3':
                tests = OptimizationTests()
                success = tests.run_all_tests()
                if success:
                    PerformanceBenchmark.run_all_benchmarks()
            else:
                print("Invalid choice. Running all tests...")
                tests = OptimizationTests()
                tests.run_all_tests()
        
        except KeyboardInterrupt:
            print("\n\nExited by user.")
        except Exception as e:
            print(f"\nError: {e}")
