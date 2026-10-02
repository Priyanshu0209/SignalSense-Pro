import React, { useState } from 'react';
import { Database, Target } from 'lucide-react';
import { CalibrationStudio } from './CalibrationStudio';
import { DatasetDashboard } from './DatasetDashboard';
import { ConnectedDevice } from '../types/device';

interface DataStudioProps {
  devices: ConnectedDevice[];
}

export const DataStudio: React.FC<DataStudioProps> = ({ devices }) => {
  const [activeSubTab, setActiveSubTab] = useState<'calibration' | 'dataset'>('calibration');

  return (
    <div className="w-full h-full flex flex-col bg-[#020617]">
      {/* Top Navigation for Data Studio */}
      <div className="flex border-b border-border/50 bg-background-secondary/80 backdrop-blur-md px-6 pt-4 gap-4">
        <button
          onClick={() => setActiveSubTab('calibration')}
          className={`pb-3 px-2 flex items-center gap-2 font-bold tracking-widest text-sm transition-all border-b-2 ${
            activeSubTab === 'calibration'
              ? 'border-cyan-400 text-cyan-400'
              : 'border-transparent text-text-muted hover:text-text-primary'
          }`}
        >
          <Target size={18} /> CALIBRATION
        </button>
        <button
          onClick={() => setActiveSubTab('dataset')}
          className={`pb-3 px-2 flex items-center gap-2 font-bold tracking-widest text-sm transition-all border-b-2 ${
            activeSubTab === 'dataset'
              ? 'border-cyan-400 text-cyan-400'
              : 'border-transparent text-text-muted hover:text-text-primary'
          }`}
        >
          <Database size={18} /> DATASETS
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-hidden">
        {activeSubTab === 'calibration' && <CalibrationStudio />}
        {activeSubTab === 'dataset' && <DatasetDashboard devices={devices} />}
      </div>
    </div>
  );
};
