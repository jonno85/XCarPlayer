import React, { useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StatusBar } from 'expo-status-bar';
import { setupPlayer } from './src/services/player';
import { registerCarPlay } from './src/services/carplay';
import Navigation from './src/navigation';

const queryClient = new QueryClient();

export default function App() {
  useEffect(() => {
    setupPlayer();
    registerCarPlay();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <StatusBar style="light" />
      <Navigation />
    </QueryClientProvider>
  );
}
