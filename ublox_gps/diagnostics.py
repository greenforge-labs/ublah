"""
Diagnostics and Health Monitoring for Ublox GPS system.
Provides comprehensive system health checks, performance monitoring, and diagnostic reporting.
"""

import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """System health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    OFFLINE = "offline"


@dataclass
class HealthCheck:
    """Individual health check result."""
    component: str
    status: HealthStatus
    message: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance monitoring metrics."""
    component: str
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_counts: Dict[str, int] = field(default_factory=dict)
    success_count: int = 0
    total_operations: int = 0
    last_operation_time: Optional[datetime] = None
    
    @property
    def average_response_time(self) -> float:
        """Calculate average response time in seconds."""
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        return (self.success_count / self.total_operations * 100) if self.total_operations > 0 else 0.0
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage."""
        return 100.0 - self.success_rate


class SystemDiagnostics:
    """Comprehensive system diagnostics and health monitoring."""
    
    def __init__(self, config):
        self.config = config
        self.health_checks: List[HealthCheck] = []
        self.performance_metrics: Dict[str, PerformanceMetrics] = {}
        self.diagnostic_history = deque(maxlen=1000)
        self.monitoring_enabled = getattr(config, 'diagnostics_enabled', True)
        self.health_check_interval = getattr(config, 'health_check_interval_seconds', 60)
        self.performance_monitoring_enabled = getattr(config, 'performance_monitoring_enabled', True)
        
        # Component monitoring
        self.components = ['gps_handler', 'ntrip_client', 'rtcm_handler', 'ha_interface']
        for component in self.components:
            self.performance_metrics[component] = PerformanceMetrics(component=component)
        
        # Health monitoring task
        self._health_monitor_task: Optional[asyncio.Task] = None
        self._stop_monitoring = asyncio.Event()
        
        logger.info(f"System diagnostics initialized - monitoring: {self.monitoring_enabled}")
    
    async def start_monitoring(self) -> None:
        """Start continuous health monitoring."""
        if not self.monitoring_enabled:
            return
        
        self._health_monitor_task = asyncio.create_task(self._health_monitoring_loop())
        logger.info("Health monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        self._stop_monitoring.set()
        if self._health_monitor_task:
            try:
                await asyncio.wait_for(self._health_monitor_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._health_monitor_task.cancel()
        logger.info("Health monitoring stopped")
    
    async def _health_monitoring_loop(self) -> None:
        """Continuous health monitoring loop."""
        while not self._stop_monitoring.is_set():
            try:
                await self.perform_health_checks()
                await asyncio.wait_for(
                    self._stop_monitoring.wait(), 
                    timeout=self.health_check_interval
                )
            except asyncio.TimeoutError:
                continue  # Normal timeout, continue monitoring
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    def record_operation(self, component: str, operation: str, 
                        duration: float, success: bool, 
                        error_details: Optional[str] = None) -> None:
        """Record performance metrics for an operation."""
        if not self.performance_monitoring_enabled:
            return
        
        if component not in self.performance_metrics:
            self.performance_metrics[component] = PerformanceMetrics(component=component)
        
        metrics = self.performance_metrics[component]
        metrics.response_times.append(duration)
        metrics.total_operations += 1
        metrics.last_operation_time = datetime.now()
        
        if success:
            metrics.success_count += 1
        else:
            error_type = error_details or "unknown_error"
            metrics.error_counts[error_type] = metrics.error_counts.get(error_type, 0) + 1
    
    def log_error(self, error_message: str, component: str = "system") -> None:
        """Log an error and record it in diagnostics."""
        logger.error(f"{component}: {error_message}")
        
        # Record in diagnostic history
        self.diagnostic_history.append({
            'timestamp': datetime.now(),
            'level': 'ERROR',
            'component': component,
            'message': error_message
        })
        
        # Update performance metrics
        if component in self.performance_metrics:
            error_type = "logged_error"
            self.performance_metrics[component].error_counts[error_type] = \
                self.performance_metrics[component].error_counts.get(error_type, 0) + 1
    
    async def perform_health_checks(self) -> List[HealthCheck]:
        """Perform comprehensive system health checks."""
        current_checks = []
        
        try:
            # GPS Handler Health Check
            gps_health = await self._check_gps_handler_health()
            current_checks.append(gps_health)
            
            # NTRIP Client Health Check
            ntrip_health = await self._check_ntrip_client_health()
            current_checks.append(ntrip_health)
            
            # RTCM Handler Health Check
            rtcm_health = await self._check_rtcm_handler_health()
            current_checks.append(rtcm_health)
            
            # System Resource Health Check
            system_health = await self._check_system_resources()
            current_checks.append(system_health)
            
            # Configuration Health Check
            config_health = await self._check_configuration_health()
            current_checks.append(config_health)
            
            # Update health status
            self.health_checks = current_checks
            self.diagnostic_history.append({
                'timestamp': datetime.now(),
                'checks': current_checks,
                'overall_status': self._determine_overall_status(current_checks)
            })
            
            return current_checks
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            error_check = HealthCheck(
                component="diagnostics",
                status=HealthStatus.CRITICAL,
                message=f"Health check system error: {str(e)}",
                timestamp=datetime.now()
            )
            return [error_check]
    
    async def _check_gps_handler_health(self) -> HealthCheck:
        """Check GPS handler health status."""
        component = "gps_handler"
        metrics = self.performance_metrics.get(component)
        
        if not metrics or not metrics.last_operation_time:
            return HealthCheck(
                component=component,
                status=HealthStatus.OFFLINE,
                message="No GPS operations recorded",
                timestamp=datetime.now()
            )
        
        # Check if GPS operations are recent
        time_since_last = datetime.now() - metrics.last_operation_time
        if time_since_last > timedelta(minutes=5):
            return HealthCheck(
                component=component,
                status=HealthStatus.CRITICAL,
                message=f"No GPS activity for {time_since_last.total_seconds():.0f} seconds",
                timestamp=datetime.now(),
                details={'last_operation': metrics.last_operation_time.isoformat()}
            )
        
        # Check success rate
        if metrics.success_rate < 50:
            return HealthCheck(
                component=component,
                status=HealthStatus.CRITICAL,
                message=f"Low GPS success rate: {metrics.success_rate:.1f}%",
                timestamp=datetime.now(),
                details={'success_rate': metrics.success_rate, 'error_counts': dict(metrics.error_counts)}
            )
        elif metrics.success_rate < 80:
            return HealthCheck(
                component=component,
                status=HealthStatus.WARNING,
                message=f"Moderate GPS success rate: {metrics.success_rate:.1f}%",
                timestamp=datetime.now(),
                details={'success_rate': metrics.success_rate}
            )
        
        return HealthCheck(
            component=component,
            status=HealthStatus.HEALTHY,
            message=f"GPS operating normally (success rate: {metrics.success_rate:.1f}%)",
            timestamp=datetime.now(),
            details={'avg_response_time': metrics.average_response_time}
        )
    
    async def _check_ntrip_client_health(self) -> HealthCheck:
        """Check NTRIP client health status."""
        component = "ntrip_client"
        metrics = self.performance_metrics.get(component)
        
        if not metrics or not metrics.last_operation_time:
            return HealthCheck(
                component=component,
                status=HealthStatus.WARNING,
                message="No NTRIP operations recorded",
                timestamp=datetime.now()
            )
        
        # Check connection status based on recent activity
        time_since_last = datetime.now() - metrics.last_operation_time
        if time_since_last > timedelta(minutes=2):
            return HealthCheck(
                component=component,
                status=HealthStatus.CRITICAL,
                message=f"NTRIP connection inactive for {time_since_last.total_seconds():.0f} seconds",
                timestamp=datetime.now()
            )
        
        # Check for connection stability
        if metrics.error_rate > 20:
            return HealthCheck(
                component=component,
                status=HealthStatus.WARNING,
                message=f"High NTRIP error rate: {metrics.error_rate:.1f}%",
                timestamp=datetime.now(),
                details={'error_counts': dict(metrics.error_counts)}
            )
        
        return HealthCheck(
            component=component,
            status=HealthStatus.HEALTHY,
            message="NTRIP connection stable",
            timestamp=datetime.now(),
            details={'success_rate': metrics.success_rate}
        )
    
    async def _check_rtcm_handler_health(self) -> HealthCheck:
        """Check RTCM handler health status."""
        component = "rtcm_handler"
        
        # This would check RTCM message processing health
        # For now, return a basic health check
        return HealthCheck(
            component=component,
            status=HealthStatus.HEALTHY,
            message="RTCM processing operational",
            timestamp=datetime.now()
        )
    
    async def _check_system_resources(self) -> HealthCheck:
        """Check system resource usage."""
        component = "system_resources"
        
        try:
            import psutil
            
            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                return HealthCheck(
                    component=component,
                    status=HealthStatus.CRITICAL,
                    message=f"High memory usage: {memory.percent:.1f}%",
                    timestamp=datetime.now(),
                    details={'memory_percent': memory.percent}
                )
            elif memory.percent > 80:
                return HealthCheck(
                    component=component,
                    status=HealthStatus.WARNING,
                    message=f"Elevated memory usage: {memory.percent:.1f}%",
                    timestamp=datetime.now(),
                    details={'memory_percent': memory.percent}
                )
            
            return HealthCheck(
                component=component,
                status=HealthStatus.HEALTHY,
                message=f"System resources normal (memory: {memory.percent:.1f}%)",
                timestamp=datetime.now(),
                details={'memory_percent': memory.percent}
            )
            
        except ImportError:
            return HealthCheck(
                component=component,
                status=HealthStatus.WARNING,
                message="System monitoring unavailable (psutil not installed)",
                timestamp=datetime.now()
            )
        except Exception as e:
            return HealthCheck(
                component=component,
                status=HealthStatus.WARNING,
                message=f"System monitoring error: {str(e)}",
                timestamp=datetime.now()
            )
    
    async def _check_configuration_health(self) -> HealthCheck:
        """Check configuration validity."""
        component = "configuration"
        
        try:
            # Validate critical configuration parameters
            issues = []
            
            if not hasattr(self.config, 'gps_device') or not self.config.gps_device:
                issues.append("GPS device not configured")
            
            if not hasattr(self.config, 'gps_baudrate') or self.config.gps_baudrate <= 0:
                issues.append("Invalid GPS baudrate")
            
            if (hasattr(self.config, 'ntrip_enabled') and self.config.ntrip_enabled and 
                not hasattr(self.config, 'ntrip_host')):
                issues.append("NTRIP enabled but host not configured")
            
            if issues:
                return HealthCheck(
                    component=component,
                    status=HealthStatus.CRITICAL,
                    message=f"Configuration issues: {', '.join(issues)}",
                    timestamp=datetime.now(),
                    details={'issues': issues}
                )
            
            return HealthCheck(
                component=component,
                status=HealthStatus.HEALTHY,
                message="Configuration valid",
                timestamp=datetime.now()
            )
            
        except Exception as e:
            return HealthCheck(
                component=component,
                status=HealthStatus.WARNING,
                message=f"Configuration check error: {str(e)}",
                timestamp=datetime.now()
            )
    
    def _determine_overall_status(self, checks: List[HealthCheck]) -> HealthStatus:
        """Determine overall system health status."""
        if not checks:
            return HealthStatus.OFFLINE
        
        statuses = [check.status for check in checks]
        
        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            return HealthStatus.WARNING
        elif HealthStatus.OFFLINE in statuses:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary."""
        if not self.health_checks:
            return {
                'overall_status': HealthStatus.OFFLINE.value,
                'message': 'No health data available',
                'components': {},
                'last_check': None
            }
        
        overall_status = self._determine_overall_status(self.health_checks)
        
        return {
            'overall_status': overall_status.value,
            'last_check': max(check.timestamp for check in self.health_checks).isoformat(),
            'components': {
                check.component: {
                    'status': check.status.value,
                    'message': check.message,
                    'timestamp': check.timestamp.isoformat(),
                    'details': check.details
                }
                for check in self.health_checks
            },
            'performance_metrics': {
                component: {
                    'average_response_time': metrics.average_response_time,
                    'success_rate': metrics.success_rate,
                    'total_operations': metrics.total_operations,
                    'error_counts': dict(metrics.error_counts),
                    'last_operation': metrics.last_operation_time.isoformat() if metrics.last_operation_time else None
                }
                for component, metrics in self.performance_metrics.items()
            }
        }
    
    def get_diagnostic_report(self) -> Dict[str, Any]:
        """Generate comprehensive diagnostic report."""
        return {
            'timestamp': datetime.now().isoformat(),
            'health_summary': self.get_health_summary(),
            'system_info': {
                'monitoring_enabled': self.monitoring_enabled,
                'performance_monitoring_enabled': self.performance_monitoring_enabled,
                'health_check_interval': self.health_check_interval,
                'diagnostic_history_length': len(self.diagnostic_history)
            },
            'recent_history': [
                {
                    'timestamp': entry['timestamp'].isoformat(),
                    'overall_status': entry['overall_status'].value,
                    'component_count': len(entry['checks'])
                }
                for entry in list(self.diagnostic_history)[-10:]  # Last 10 entries
            ]
        }
