import React from 'react';
import { ConnectedDevice } from '../hooks/useNetworkData';
import { Wifi, Search, Hash, Server, Activity, Clock, Layers } from 'lucide-react';

interface DevicesListProps {
  devices: ConnectedDevice[];
}

export const DevicesList: React.FC<DevicesListProps> = ({ devices }) => {
  return (
    <div className="w-full h-full flex flex-col p-6 bg-background-primary overflow-y-auto custom-scrollbar">
      <h2 className="text-2xl font-black text-text-primary tracking-widest mb-6">CONNECTED DEVICES</h2>
      
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {devices.length === 0 ? (
          <div className="col-span-full py-12 flex flex-col items-center justify-center text-text-muted bg-card/30 rounded-2xl border border-border">
            <Search size={48} className="mb-4 opacity-50" />
            <p className="text-lg font-bold tracking-wider">No Devices Found</p>
            <p className="text-sm mt-2">Waiting for telemetry from the hardware...</p>
          </div>
        ) : (
          devices.map(device => {
            const isOnline = device.online_status;
            const distance = device.distance?.value;
            const rssi = device.current_rssi?.value;
            const quality = device.health_score || 'Unavailable';

            return (
              <div key={device.mac_address} className="bg-card border border-border p-5 rounded-2xl flex flex-col gap-4 shadow-lg hover:border-accent-primary/50 transition-all">
                
                {/* Header */}
                <div className="flex justify-between items-start border-b border-border pb-3">
                  <div className="flex flex-col">
                    <h3 className="text-lg font-bold text-text-primary">{device.hostname || 'Unknown Device'}</h3>
                    <span className="text-xs text-text-muted font-mono">{device.manufacturer || 'Unknown Manufacturer'}</span>
                  </div>
                  <div className={`px-3 py-1 rounded-full text-xs font-bold tracking-widest border ${
                    isOnline ? 'bg-status-success/10 text-status-success border-status-success/30' : 'bg-status-error/10 text-status-error border-status-error/30'
                  }`}>
                    {isOnline ? 'ONLINE' : 'OFFLINE'}
                  </div>
                </div>

                {/* Details Grid */}
                <div className="grid grid-cols-2 gap-y-4 gap-x-2 text-sm">
                  
                  <div className="flex items-center gap-2">
                    <Hash size={16} className="text-text-muted" />
                    <span className="text-text-secondary">MAC:</span>
                    <span className="font-mono font-medium text-text-primary">{device.mac_address}</span>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Server size={16} className="text-text-muted" />
                    <span className="text-text-secondary">IP:</span>
                    <span className="font-mono font-medium text-text-primary">{device.ip_address || 'Unavailable'}</span>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Wifi size={16} className="text-text-muted" />
                    <span className="text-text-secondary">RSSI:</span>
                    <span className="font-mono font-medium text-text-primary">{rssi !== null && rssi !== undefined ? `${rssi} dBm` : 'Unavailable'}</span>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Layers size={16} className="text-text-muted" />
                    <span className="text-text-secondary">Distance:</span>
                    <span className="font-mono font-medium text-text-primary">{distance !== null && distance !== undefined ? `${distance.toFixed(2)} m` : 'Calibration Required'}</span>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Activity size={16} className="text-text-muted" />
                    <span className="text-text-secondary">Signal Quality:</span>
                    <span className="font-mono font-medium text-text-primary">{quality}</span>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Clock size={16} className="text-text-muted" />
                    <span className="text-text-secondary">Conn. Time:</span>
                    <span className="font-mono font-medium text-text-primary">{device.last_seen ? new Date(device.last_seen).toLocaleTimeString() : 'Unavailable'}</span>
                  </div>
                  
                </div>

              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
