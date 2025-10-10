import os, json, time, asyncio, logging
from typing import Dict, Any, List, Optional, Protocol
from datetime import datetime
import httpx
from collections import deque
from threading import Lock

logger = logging.getLogger(__name__)


class SIEMShipper(Protocol):
    """Protocol for SIEM integration implementations."""
    def ship(self, record: Dict[str, Any]) -> None:
        """Ship a single audit record to SIEM."""
        ...
    
    def ship_batch(self, records: List[Dict[str, Any]]) -> None:
        """Ship a batch of audit records to SIEM."""
        ...


class SplunkHECShipper:
    """Splunk HTTP Event Collector integration."""
    
    def __init__(self, hec_url: str, hec_token: str, source: str = "mcp_redaction", sourcetype: str = "_json"):
        self.hec_url = hec_url.rstrip("/") + "/services/collector/event"
        self.hec_token = hec_token
        self.source = source
        self.sourcetype = sourcetype
        self.client = httpx.Client(timeout=5.0)
    
    def ship(self, record: Dict[str, Any]) -> None:
        """Ship single record to Splunk HEC."""
        try:
            payload = {
                "time": record.get("ts", time.time()),
                "host": os.getenv("HOSTNAME", "mcp-server"),
                "source": self.source,
                "sourcetype": self.sourcetype,
                "event": record
            }
            
            response = self.client.post(
                self.hec_url,
                json=payload,
                headers={"Authorization": f"Splunk {self.hec_token}"}
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to ship to Splunk: {e}")
    
    def ship_batch(self, records: List[Dict[str, Any]]) -> None:
        """Ship batch of records to Splunk HEC."""
        for record in records:
            self.ship(record)


class ElasticsearchShipper:
    """Elasticsearch/ELK Stack integration."""
    
    def __init__(self, es_url: str, index: str = "mcp-audit", api_key: Optional[str] = None):
        self.es_url = es_url.rstrip("/")
        self.index = index
        self.api_key = api_key
        self.client = httpx.Client(timeout=5.0)
    
    def ship(self, record: Dict[str, Any]) -> None:
        """Ship single record to Elasticsearch."""
        try:
            # Add @timestamp for Elasticsearch
            record["@timestamp"] = record.get("ts", datetime.utcnow().isoformat())
            
            # Use daily indices
            date_suffix = datetime.utcnow().strftime("%Y.%m.%d")
            index_name = f"{self.index}-{date_suffix}"
            
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"ApiKey {self.api_key}"
            
            response = self.client.post(
                f"{self.es_url}/{index_name}/_doc",
                json=record,
                headers=headers
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to ship to Elasticsearch: {e}")
    
    def ship_batch(self, records: List[Dict[str, Any]]) -> None:
        """Ship batch using _bulk API."""
        if not records:
            return
        
        try:
            date_suffix = datetime.utcnow().strftime("%Y.%m.%d")
            index_name = f"{self.index}-{date_suffix}"
            
            # Build bulk request
            bulk_data = []
            for record in records:
                record["@timestamp"] = record.get("ts", datetime.utcnow().isoformat())
                bulk_data.append(json.dumps({"index": {"_index": index_name}}))
                bulk_data.append(json.dumps(record))
            
            bulk_body = "\n".join(bulk_data) + "\n"
            
            headers = {"Content-Type": "application/x-ndjson"}
            if self.api_key:
                headers["Authorization"] = f"ApiKey {self.api_key}"
            
            response = self.client.post(
                f"{self.es_url}/_bulk",
                content=bulk_body,
                headers=headers
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to ship batch to Elasticsearch: {e}")


class DatadogShipper:
    """Datadog Logs API integration."""
    
    def __init__(self, api_key: str, site: str = "datadoghq.com", service: str = "mcp-redaction"):
        self.api_key = api_key
        self.intake_url = f"https://http-intake.logs.{site}/api/v2/logs"
        self.service = service
        self.client = httpx.Client(timeout=5.0)
    
    def ship(self, record: Dict[str, Any]) -> None:
        """Ship single record to Datadog."""
        try:
            payload = {
                "ddsource": "mcp-redaction",
                "ddtags": f"env:{record.get('env', 'unknown')},caller:{record.get('caller', 'unknown')}",
                "hostname": os.getenv("HOSTNAME", "mcp-server"),
                "message": json.dumps(record),
                "service": self.service
            }
            
            response = self.client.post(
                self.intake_url,
                json=[payload],  # Datadog expects array
                headers={
                    "DD-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to ship to Datadog: {e}")
    
    def ship_batch(self, records: List[Dict[str, Any]]) -> None:
        """Ship batch to Datadog."""
        if not records:
            return
        
        try:
            payloads = []
            for record in records:
                payloads.append({
                    "ddsource": "mcp-redaction",
                    "ddtags": f"env:{record.get('env', 'unknown')},caller:{record.get('caller', 'unknown')}",
                    "hostname": os.getenv("HOSTNAME", "mcp-server"),
                    "message": json.dumps(record),
                    "service": self.service
                })
            
            response = self.client.post(
                self.intake_url,
                json=payloads,
                headers={
                    "DD-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to ship batch to Datadog: {e}")


class SyslogShipper:
    """Syslog (RFC 5424) integration for traditional SIEM systems."""
    
    def __init__(self, syslog_host: str, syslog_port: int = 514, facility: int = 16):
        import socket
        self.host = syslog_host
        self.port = syslog_port
        self.facility = facility
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    def ship(self, record: Dict[str, Any]) -> None:
        """Ship record as syslog message."""
        try:
            # RFC 5424 format
            priority = self.facility * 8 + 6  # INFO level
            timestamp = datetime.utcnow().isoformat() + "Z"
            hostname = os.getenv("HOSTNAME", "mcp-server")
            app_name = "mcp-redaction"
            
            message = json.dumps(record)
            syslog_msg = f"<{priority}>1 {timestamp} {hostname} {app_name} - - - {message}"
            
            self.sock.sendto(syslog_msg.encode('utf-8'), (self.host, self.port))
        except Exception as e:
            logger.error(f"Failed to ship to syslog: {e}")
    
    def ship_batch(self, records: List[Dict[str, Any]]) -> None:
        """Ship batch via syslog."""
        for record in records:
            self.ship(record)


class BufferedSIEMShipper:
    """Buffered shipper with async batch processing."""
    
    def __init__(self, shipper: SIEMShipper, batch_size: int = 100, flush_interval: float = 5.0):
        self.shipper = shipper
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.buffer: deque = deque(maxlen=1000)  # Max 1000 records in buffer
        self.lock = Lock()
        self.last_flush = time.time()
    
    def ship(self, record: Dict[str, Any]) -> None:
        """Add record to buffer and flush if needed."""
        with self.lock:
            self.buffer.append(record)
            
            # Flush if batch size reached or interval expired
            should_flush = (
                len(self.buffer) >= self.batch_size or
                time.time() - self.last_flush >= self.flush_interval
            )
            
            if should_flush:
                self._flush()
    
    def _flush(self):
        """Flush buffer to SIEM."""
        if not self.buffer:
            return
        
        # Get all records from buffer
        records = list(self.buffer)
        self.buffer.clear()
        self.last_flush = time.time()
        
        # Ship in background to avoid blocking
        try:
            self.shipper.ship_batch(records)
        except Exception as e:
            logger.error(f"Failed to flush buffer: {e}")
    
    def ship_batch(self, records: List[Dict[str, Any]]) -> None:
        """Ship batch directly."""
        self.shipper.ship_batch(records)


class AuditLogger:
    """Enhanced audit logger with SIEM integration."""
    
    def __init__(self, path: str, siem_shipper: Optional[SIEMShipper] = None):
        self.path = path
        self.siem_shipper = siem_shipper
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def write(self, record: Dict[str, Any]):
        """Write to local JSONL and optionally ship to SIEM."""
        # Always write to local file (immutable audit trail)
        line = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        
        # Ship to SIEM if configured
        if self.siem_shipper:
            try:
                self.siem_shipper.ship(record)
            except Exception as e:
                logger.error(f"SIEM shipping failed: {e}")

    def query(self, q: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Query local audit logs."""
        results = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in reversed(f.readlines()):
                    if len(results) >= limit:
                        break
                    obj = json.loads(line)
                    if not q or q.lower() in line.lower():
                        results.append(obj)
        except FileNotFoundError:
            pass
        return results
