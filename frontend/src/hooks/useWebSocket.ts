import { useEffect, useRef, useState } from 'react';
import { DeviceState } from '../types';

// Using native WebSocket since backend is FastAPI standard websockets, 
// wait, we installed socket.io-client earlier but backend uses native FastAPI websockets. 
// We should use native browser WebSocket for FastAPI.

export function useSignalSenseWebSocket(url: string) {
  const [devices, setDevices] = useState<Record<string, DeviceState>>({});
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Initial fetch to populate state before WS events come in
    fetch('http://127.0.0.1:8000/api/v1/devices')
      .then(res => res.json())
      .then((res: Record<string, unknown>) => {
        const data = (res.data || res) as Array<Record<string, unknown>>;
        const initialMap: Record<string, DeviceState> = {};
        data.forEach((d) => {
          initialMap[d.mac_address as string] = {
            mac: d.mac_address as string,
            hostname: d.hostname as string,
            ip: d.ip_address as string,
            manufacturer: d.manufacturer as string,
            rssi: d.current_rssi as number,
            signal: d.signal_classification as string,
            distance: d.distance_classification as string,
            trend: d.signal_trend as string,
            animation: d.animation_state as string,
            status: d.online_status ? "online" : "offline",
            connection_duration: d.connection_duration as number,
            timestamp: d.last_seen as string
          };
        });
        setDevices(initialMap);
      })
      .catch(console.error);

    const connect = () => {
      ws.current = new WebSocket(url);
      
      ws.current.onopen = () => {
        setIsConnected(true);
        // Heartbeat
        setInterval(() => {
          if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send("ping");
          }
        }, 30000);
      };

      ws.current.onclose = () => {
        setIsConnected(false);
        // Reconnect after 3 seconds
        setTimeout(connect, 3000);
      };

      ws.current.onmessage = (event) => {
        if (event.data === "pong") return;
        
        try {
          const payload = JSON.parse(event.data);
          if (payload.event === "device_updated" && Array.isArray(payload.data)) {
            setDevices(prev => {
              const next = { ...prev };
              payload.data.forEach((update: DeviceState) => {
                next[update.mac] = { ...next[update.mac], ...update };
              });
              return next;
            });
          }
        } catch (e) {
          console.error("WS Parse Error", e);
        }
      };
    };

    connect();

    return () => {
      ws.current?.close();
    };
  }, [url]);

  return { devices: Object.values(devices), isConnected };
}
