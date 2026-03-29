import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Text } from 'react-native';

import LibraryScreen from '../screens/LibraryScreen';
import PlaylistScreen from '../screens/PlaylistScreen';
import PlayerScreen from '../screens/PlayerScreen';
import SettingsScreen from '../screens/SettingsScreen';

const Tab = createBottomTabNavigator();
const LibraryStack = createNativeStackNavigator();

function LibraryNavigator() {
  return (
    <LibraryStack.Navigator screenOptions={{ headerStyle: { backgroundColor: '#111' }, headerTintColor: '#fff' }}>
      <LibraryStack.Screen name="Library" component={LibraryScreen} />
      <LibraryStack.Screen name="Playlist" component={PlaylistScreen} options={({ route }) => ({ title: route.params.playlist.name })} />
      <LibraryStack.Screen name="Player" component={PlayerScreen} options={{ title: 'Now Playing' }} />
    </LibraryStack.Navigator>
  );
}

export default function Navigation() {
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
          component={LibraryNavigator}
          options={{ title: 'Library', tabBarIcon: ({ color }) => <Text style={{ color }}>♪</Text> }}
        />
        <Tab.Screen
          name="PlayerTab"
          component={PlayerScreen}
          options={{ title: 'Now Playing', tabBarIcon: ({ color }) => <Text style={{ color }}>▶</Text> }}
        />
        <Tab.Screen
          name="SettingsTab"
          component={SettingsScreen}
          options={{ title: 'Settings', tabBarIcon: ({ color }) => <Text style={{ color }}>⚙</Text>, headerShown: true, headerStyle: { backgroundColor: '#111' }, headerTintColor: '#fff' }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
