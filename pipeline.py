"""
CUDA-Accelerated Frame Processing Pipeline
Handles GPU preprocessing, CLAHE enhancement, and automatic CPU fallback
Part of NeuroGaze Elite
"""

import cv2
import numpy as np
import logging
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeviceBackend(Enum):
    """Supported compute backends"""
    CUDA = "CUDA"
    CPU = "CPU"


@dataclass
class GPUDeviceInfo:
    """Information about detected GPU device"""
    device_id: int
    device_name: str
    compute_capability: Tuple[int, int]
    total_memory_mb: int
    backend: DeviceBackend


class CUDAPipeline:
    """
    GPU-accelerated preprocessing pipeline with automatic CPU fallback.
    Fixes GAP 1: Real CUDA OpenCV preprocessing with GPU tensor support.
    """

    def __init__(self, enable_cuda: bool = True, target_width: int = 640, target_height: int = 480):
        """
        Initialize CUDA pipeline.
        
        Args:
            enable_cuda: Try to use CUDA if available
            target_width: Frame processing width
            target_height: Frame processing height
        """
        self.target_width = target_width
        self.target_height = target_height
        self.backend = DeviceBackend.CPU
        self.device_info: Optional[GPUDeviceInfo] = None
        self.clahe_gpu: Optional[cv2.cuda.CLAHE] = None
        self.cuda_enabled = False

        # Detect and initialize CUDA if requested
        if enable_cuda:
            self._init_cuda()
        else:
            logger.info("CUDA disabled by user, using CPU pipeline")

        self._print_startup_info()

    def _init_cuda(self) -> None:
        """Initialize CUDA if available with automatic fallback"""
        try:
            # Check CUDA availability
            cuda_device_count = cv2.cuda.getCudaEnabledDeviceCount()
            
            if cuda_device_count == 0:
                logger.warning("No CUDA-enabled devices detected, falling back to CPU")
                return

            # Get current device info
            cv2.cuda.setDevice(0)
            device_id = cv2.cuda.getDevice()
            
            try:
                device_name = cv2.cuda.getDeviceName(device_id)
                compute_capability = cv2.cuda.deviceSupportsFeatures(device_id)
                total_memory = cv2.cuda.getDeviceProperties(device_id)
                
                self.device_info = GPUDeviceInfo(
                    device_id=device_id,
                    device_name=device_name,
                    compute_capability=compute_capability,
                    total_memory_mb=0,  # OpenCV doesn't expose this directly
                    backend=DeviceBackend.CUDA
                )
                
                # Initialize GPU-accelerated CLAHE
                self.clahe_gpu = cv2.cuda.createCLAHE(
                    clipLimit=2.0,
                    tileGridSize=(8, 8)
                )
                
                self.backend = DeviceBackend.CUDA
                self.cuda_enabled = True
                logger.info(f"✓ CUDA initialized on device: {device_name}")
                
            except Exception as e:
                logger.warning(f"Failed to get CUDA device info: {e}, using CPU fallback")
                self.backend = DeviceBackend.CPU
                
        except Exception as e:
            logger.warning(f"CUDA initialization failed: {e}, falling back to CPU pipeline")
            self.backend = DeviceBackend.CPU

    def _print_startup_info(self) -> None:
        """Print GPU/CPU startup information"""
        if self.cuda_enabled:
            logger.info(f"🚀 NeuroGaze Elite - GPU-Accelerated Pipeline")
            logger.info(f"   Backend: {self.device_info.device_name} ({self.backend.value})")
            logger.info(f"   Target FPS: 30 (GPU-optimized)")
            logger.info(f"   Target latency: <20ms")
        else:
            logger.info(f"🚀 NeuroGaze Elite - CPU Pipeline")
            logger.info(f"   Backend: CPU (single-threaded)")
            logger.info(f"   Target FPS: 30 (CPU-optimized)")
            logger.info(f"   Target latency: <50ms")

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Process a single frame through the preprocessing pipeline.
        
        Args:
            frame: Input BGR frame from camera (np.ndarray)
            
        Returns:
            Processed frame ready for MediaPipe (np.ndarray)
        """
        if self.cuda_enabled:
            return self._process_frame_gpu(frame)
        else:
            return self._process_frame_cpu(frame)

    def _process_frame_gpu(self, frame: np.ndarray) -> np.ndarray:
        """GPU-accelerated frame processing pipeline"""
        try:
            # Upload to GPU
            gpu_frame = cv2.cuda_GpuMat()
            gpu_frame.upload(frame)

            # Resize on GPU
            h, w = frame.shape[:2]
            if w != self.target_width or h != self.target_height:
                gpu_resized = cv2.cuda.resize(
                    gpu_frame,
                    (self.target_width, self.target_height)
                )
            else:
                gpu_resized = gpu_frame

            # Convert BGR to YCrCb on GPU for CLAHE processing
            gpu_ycrcb = cv2.cuda.cvtColor(gpu_resized, cv2.COLOR_BGR2YCrCb)

            # Extract Y channel
            gpu_y_channel = cv2.cuda.split(gpu_ycrcb)[0]

            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) on GPU
            # Improves visibility in low-light conditions
            gpu_clahe_y = self.clahe_gpu.apply(gpu_y_channel)

            # Merge channels back
            gpu_cr, gpu_cb = cv2.cuda.split(gpu_ycrcb)[1:]
            gpu_ycrcb_enhanced = cv2.cuda.merge([gpu_clahe_y, gpu_cr, gpu_cb])

            # Convert back to BGR on GPU
            gpu_bgr_enhanced = cv2.cuda.cvtColor(gpu_ycrcb_enhanced, cv2.COLOR_YCrCb2BGR)

            # Apply slight sharpening on GPU
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            gpu_sharpened = cv2.cuda.morphologyEx(gpu_bgr_enhanced, cv2.MORPH_GRADIENT, kernel)

            # Blend sharpened result (20% sharpening)
            gpu_output = cv2.cuda.addWeighted(gpu_bgr_enhanced, 0.8, gpu_sharpened, 0.2, 0)

            # Download from GPU
            processed_frame = gpu_output.download()

            return processed_frame

        except Exception as e:
            logger.error(f"GPU processing failed: {e}, falling back to CPU")
            self.backend = DeviceBackend.CPU
            self.cuda_enabled = False
            return self._process_frame_cpu(frame)

    def _process_frame_cpu(self, frame: np.ndarray) -> np.ndarray:
        """CPU-based frame processing pipeline (fallback)"""
        # Resize
        h, w = frame.shape[:2]
        if w != self.target_width or h != self.target_height:
            resized = cv2.resize(frame, (self.target_width, self.target_height))
        else:
            resized = frame.copy()

        # Convert to YCrCb
        ycrcb = cv2.cvtColor(resized, cv2.COLOR_BGR2YCrCb)

        # Apply CLAHE to Y channel
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        y_channel = ycrcb[:, :, 0]
        y_enhanced = clahe.apply(y_channel)

        # Merge back
        ycrcb[:, :, 0] = y_enhanced
        bgr_enhanced = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

        # Apply slight sharpening
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        sharpened = cv2.morphologyEx(bgr_enhanced, cv2.MORPH_GRADIENT, kernel)

        # Blend sharpened result (20% sharpening)
        output = cv2.addWeighted(bgr_enhanced, 0.8, sharpened, 0.2, 0)

        return output

    def resize_frame(self, frame: np.ndarray, width: int, height: int) -> np.ndarray:
        """
        Resize frame using optimal backend.
        
        Args:
            frame: Input frame
            width: Target width
            height: Target height
            
        Returns:
            Resized frame
        """
        if self.cuda_enabled:
            try:
                gpu_frame = cv2.cuda_GpuMat()
                gpu_frame.upload(frame)
                gpu_resized = cv2.cuda.resize(gpu_frame, (width, height))
                return gpu_resized.download()
            except Exception as e:
                logger.warning(f"GPU resize failed: {e}")
                return cv2.resize(frame, (width, height))
        else:
            return cv2.resize(frame, (width, height))

    def convert_colorspace(
        self, frame: np.ndarray, code: int
    ) -> np.ndarray:
        """
        Convert colorspace using optimal backend.
        
        Args:
            frame: Input frame
            code: OpenCV color conversion code
            
        Returns:
            Converted frame
        """
        if self.cuda_enabled:
            try:
                gpu_frame = cv2.cuda_GpuMat()
                gpu_frame.upload(frame)
                gpu_converted = cv2.cuda.cvtColor(gpu_frame, code)
                return gpu_converted.download()
            except Exception as e:
                logger.warning(f"GPU colorspace conversion failed: {e}")
                return cv2.cvtColor(frame, code)
        else:
            return cv2.cvtColor(frame, code)

    def apply_clahe(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply CLAHE enhancement to Y channel.
        
        Args:
            frame: BGR frame
            
        Returns:
            CLAHE-enhanced frame
        """
        if self.cuda_enabled and self.clahe_gpu is not None:
            try:
                gpu_frame = cv2.cuda_GpuMat()
                gpu_frame.upload(frame)
                gpu_ycrcb = cv2.cuda.cvtColor(gpu_frame, cv2.COLOR_BGR2YCrCb)
                channels = cv2.cuda.split(gpu_ycrcb)
                gpu_clahe_y = self.clahe_gpu.apply(channels[0])
                channels[0] = gpu_clahe_y
                gpu_ycrcb_enhanced = cv2.cuda.merge(channels)
                gpu_result = cv2.cuda.cvtColor(gpu_ycrcb_enhanced, cv2.COLOR_YCrCb2BGR)
                return gpu_result.download()
            except Exception as e:
                logger.warning(f"GPU CLAHE failed: {e}")
                return self._apply_clahe_cpu(frame)
        else:
            return self._apply_clahe_cpu(frame)

    def _apply_clahe_cpu(self, frame: np.ndarray) -> np.ndarray:
        """CPU-based CLAHE"""
        ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        y_channel = ycrcb[:, :, 0]
        ycrcb[:, :, 0] = clahe.apply(y_channel)
        return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

    def get_backend_info(self) -> dict:
        """
        Get current backend information.
        
        Returns:
            Dictionary with backend details
        """
        info = {
            "backend": self.backend.value,
            "cuda_enabled": self.cuda_enabled,
            "target_width": self.target_width,
            "target_height": self.target_height,
        }

        if self.device_info:
            info.update({
                "device_id": self.device_info.device_id,
                "device_name": self.device_info.device_name,
            })

        return info

    def cleanup(self) -> None:
        """Clean up GPU resources"""
        if self.cuda_enabled:
            try:
                cv2.cuda.resetDevice()
                logger.info("✓ CUDA resources cleaned up")
            except Exception as e:
                logger.warning(f"Error cleaning up CUDA: {e}")


# Convenience function for testing
def create_cuda_pipeline(enable_cuda: bool = True) -> CUDAPipeline:
    """Factory function to create and initialize CUDA pipeline"""
    return CUDAPipeline(enable_cuda=enable_cuda)


if __name__ == "__main__":
    # Test CUDA pipeline
    logger.info("Testing CUDAPipeline...")
    
    pipeline = CUDAPipeline(enable_cuda=True)
    logger.info(f"Backend info: {pipeline.get_backend_info()}")
    
    # Create dummy frame
    dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Process frame
    processed = pipeline.process_frame(dummy_frame)
    logger.info(f"Frame processed: {processed.shape}, dtype: {processed.dtype}")
    
    # Cleanup
    pipeline.cleanup()
    logger.info("✓ CUDAPipeline test complete")
