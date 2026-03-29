import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert } from 'react-native';
import { login, logout } from '../services/audioStation';
import { saveAgentUrl, testAgentConnection } from '../services/nasAgent';
import * as SecureStore from 'expo-secure-store';

export default function SettingsScreen() {
  const [quickConnectId, setQuickConnectId] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [agentUrl, setAgentUrl] = useState('');
  const [agentTesting, setAgentTesting] = useState(false);

  async function handleLogin() {
    if (!quickConnectId || !username || !password) {
      Alert.alert('Fill in all fields');
      return;
    }
    setLoading(true);
    try {
      await login(quickConnectId, username, password);
      Alert.alert('Connected', 'Successfully connected to your Synology NAS.');
    } catch (e) {
      Alert.alert('Connection failed', e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleLogout() {
    await logout();
    Alert.alert('Disconnected');
  }

  return (
    <View style={styles.container}>
      <Text style={styles.label}>QuickConnect ID</Text>
      <TextInput
        style={styles.input}
        placeholder="your-nas-id"
        placeholderTextColor="#555"
        autoCapitalize="none"
        value={quickConnectId}
        onChangeText={setQuickConnectId}
      />

      <Text style={styles.label}>Username</Text>
      <TextInput
        style={styles.input}
        placeholder="admin"
        placeholderTextColor="#555"
        autoCapitalize="none"
        value={username}
        onChangeText={setUsername}
      />

      <Text style={styles.label}>Password</Text>
      <TextInput
        style={styles.input}
        placeholder="••••••••"
        placeholderTextColor="#555"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />

      <TouchableOpacity style={styles.btn} onPress={handleLogin} disabled={loading}>
        <Text style={styles.btnText}>{loading ? 'Connecting…' : 'Connect to NAS'}</Text>
      </TouchableOpacity>

      <TouchableOpacity style={[styles.btn, styles.btnSecondary]} onPress={handleLogout}>
        <Text style={styles.btnText}>Disconnect</Text>
      </TouchableOpacity>

      <Text style={[styles.label, { marginTop: 32 }]}>NAS Agent URL</Text>
      <Text style={styles.hint}>e.g. http://your-nas-id.quickconnect.to:8765</Text>
      <TextInput
        style={styles.input}
        placeholder="http://..."
        placeholderTextColor="#555"
        autoCapitalize="none"
        keyboardType="url"
        value={agentUrl}
        onChangeText={setAgentUrl}
      />
      <TouchableOpacity
        style={styles.btn}
        disabled={agentTesting}
        onPress={async () => {
          if (!agentUrl) { Alert.alert('Enter the agent URL'); return; }
          setAgentTesting(true);
          try {
            await testAgentConnection(agentUrl);
            await saveAgentUrl(agentUrl);
            Alert.alert('Agent connected', 'NAS agent is reachable and saved.');
          } catch (e) {
            Alert.alert('Agent unreachable', e.message);
          } finally {
            setAgentTesting(false);
          }
        }}
      >
        <Text style={styles.btnText}>{agentTesting ? 'Testing…' : 'Save Agent URL'}</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111', padding: 24 },
  label: { color: '#aaa', fontSize: 12, marginTop: 16, marginBottom: 4 },
  input: {
    backgroundColor: '#222',
    color: '#fff',
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
  },
  btn: {
    marginTop: 24,
    backgroundColor: '#1DB954',
    borderRadius: 8,
    padding: 14,
    alignItems: 'center',
  },
  btnSecondary: { backgroundColor: '#333', marginTop: 12 },
  btnText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  hint: { color: '#555', fontSize: 11, marginBottom: 4 },
});
