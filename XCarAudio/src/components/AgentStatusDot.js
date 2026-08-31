import { View, StyleSheet } from 'react-native';

export default function AgentStatusDot({ health }) {
  const color =
    health === true ? '#1DB954' :
    health === false ? '#e74c3c' :
    '#f0a500';

  return <View style={[styles.dot, { backgroundColor: color }]} />;
}

const styles = StyleSheet.create({
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 14 },
});
