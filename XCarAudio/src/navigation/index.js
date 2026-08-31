import React, { useState, useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Text } from 'react-native';

import LibraryScreen from '../screens/LibraryScreen';
import PlaylistScreen from '../screens/PlaylistScreen';
import PlayerScreen from '../screens/PlayerScreen';
import SettingsScreen from '../screens/SettingsScreen';
import MigrationScreen from '../screens/MigrationScreen';
import AgentStatusDot from '../components/AgentStatusDot';
import { checkAgentHealth } from '../services/nasAgent';
import { getSession } from '../services/audioStation';

const Tab = createBottomTabNavigator();
const LibraryStack = createNativeStackNavigator();

function LibraryNavigator({ headerRight }) {
  return (
    <LibraryStack.Navigator screenOptions={{ headerStyle: { backgroundColor: '#111' }, headerTintColor: '#fff', headerRight }}>
      <LibraryStack.Screen name="Library" component={LibraryScreen} />
      <LibraryStack.Screen name="Playlist" component={PlaylistScreen} options={({ route }) => ({ title: route.params.playlist.name })} />
      <LibraryStack.Screen name="Player" component={PlayerScreen} options={{ title: 'Now Playing' }} />
    </LibraryStack.Navigator>
  );
}

export default function Navigation() {
  const [agentHealth, setAgentHealth] = useState(null);

  useEffect(() => {
    async function poll() {
      const session = await getSession();
      if (!session?.baseUrl) { setAgentHealth(null); return; }
      setAgentHealth(await checkAgentHealth());
    }
    poll();
    const id = setInterval(poll, 30_000);
    return () => clearInterval(id);
  }, []);

  const statusDot = () => <AgentStatusDot health={agentHealth} />;
  const headerDefaults = { headerStyle: { backgroundColor: '#111' }, headerTintColor: '#fff', headerRight: statusDot };

  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={{
          headerShown: false,
          tabBarStyle: { backgroundColor: '#111', borderTopColor: '#222' },
          tabBarActiveTintColor: '#1DB954',
          tabBarInactiveTintColor: '#666',
        }}
      >
        <Tab.Screen
          name="LibraryTab"
          options={{ title: 'Library', tabBarIcon: ({ color }) => <Text style={{ color }}>♪</Text> }}
        >
          {() => <LibraryNavigator headerRight={statusDot} />}
        </Tab.Screen>
        <Tab.Screen
          name="PlayerTab"
          component={PlayerScreen}
          options={{ title: 'Now Playing', tabBarIcon: ({ color }) => <Text style={{ color }}>▶</Text> }}
        />
        <Tab.Screen
          name="MigrateTab"
          component={MigrationScreen}
          options={{ title: 'Migrate', tabBarIcon: ({ color }) => <Text style={{ color }}>⇄</Text>, headerShown: true, ...headerDefaults }}
        />
        <Tab.Screen
          name="SettingsTab"
          component={SettingsScreen}
          options={{ title: 'Settings', tabBarIcon: ({ color }) => <Text style={{ color }}>⚙</Text>, headerShown: true, ...headerDefaults }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
