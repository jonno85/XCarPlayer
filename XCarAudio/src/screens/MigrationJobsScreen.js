/**
 * Shows live job status for an active migration.
 * Polls the NAS agent every 3 seconds for in-progress jobs.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from 'react-native';
import { getJob } from '../services/nasAgent';

const POLL_INTERVAL_MS = 3000;

const STATUS_COLOR = {
  pending: '#888',
  downloading: '#f0a500',
  done: '#1DB954',
  failed: '#e74c3c',
  queue_failed: '#e74c3c',
};

const STATUS_LABEL = {
  pending: '⏳ Pending',
  downloading: '⬇ Downloading',
  done: '✓ Done',
  failed: '✗ Failed',
  queue_failed: '✗ Queue failed',
};

export default function MigrationJobsScreen({ jobs: initialJobs, queueProgress, queuingActive, onBack }) {
  const [jobs, setJobs] = useState(initialJobs);

  // Update jobs list when new ones come in while queuing is active
  useEffect(() => {
    setJobs(initialJobs);
  }, [initialJobs]);

  // Poll active jobs
  useEffect(() => {
    const active = jobs.filter((j) => j.jobId && (j.status === 'pending' || j.status === 'downloading'));
    if (active.length === 0) return;

    const timer = setInterval(async () => {
      const updates = await Promise.allSettled(
        active.map((j) => getJob(j.jobId).then((res) => ({ jobId: j.jobId, status: res.status, error: res.error })))
      );
      setJobs((prev) =>
        prev.map((j) => {
          const update = updates.find((u) => u.status === 'fulfilled' && u.value.jobId === j.jobId);
          return update ? { ...j, status: update.value.status, error: update.value.error } : j;
        })
      );
    }, POLL_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [jobs]);

  const done = jobs.filter((j) => j.status === 'done').length;
  const failed = jobs.filter((j) => j.status === 'failed' || j.status === 'queue_failed').length;
  const total = jobs.length;

  return (
    <View style={styles.container}>
      <TouchableOpacity onPress={onBack} style={styles.backBtn}>
        <Text style={styles.backText}>← New Migration</Text>
      </TouchableOpacity>

      <View style={styles.summary}>
        <Text style={styles.heading}>Migration Progress</Text>
        {queuingActive && (
          <Text style={styles.queueStatus}>
            Queuing tracks… {Math.round(queueProgress * 100)}%
          </Text>
        )}
        <Text style={styles.counts}>
          <Text style={{ color: '#1DB954' }}>{done} done</Text>
          {'  ·  '}
          <Text style={{ color: '#e74c3c' }}>{failed} failed</Text>
          {'  ·  '}
          <Text style={{ color: '#888' }}>{total} total</Text>
        </Text>
      </View>

      <FlatList
        data={jobs}
        keyExtractor={(_, i) => String(i)}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <View style={styles.rowInfo}>
              <Text style={styles.title} numberOfLines={1}>{item.title}</Text>
              <Text style={styles.artist} numberOfLines={1}>{item.artist}</Text>
              {item.error ? <Text style={styles.errorText} numberOfLines={1}>{item.error}</Text> : null}
            </View>
            <Text style={[styles.status, { color: STATUS_COLOR[item.status] || '#888' }]}>
              {STATUS_LABEL[item.status] || item.status}
            </Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111' },
  backBtn: { paddingHorizontal: 24, paddingTop: 16 },
  backText: { color: '#1DB954', fontSize: 14 },
  summary: { paddingHorizontal: 24, paddingVertical: 16 },
  heading: { fontSize: 20, color: '#fff', fontWeight: '700', marginBottom: 4 },
  queueStatus: { fontSize: 13, color: '#f0a500', marginBottom: 4 },
  counts: { fontSize: 13, marginTop: 4 },
  row: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingVertical: 12, paddingHorizontal: 24,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#222',
  },
  rowInfo: { flex: 1, marginRight: 12 },
  title: { fontSize: 14, color: '#fff' },
  artist: { fontSize: 12, color: '#888', marginTop: 2 },
  errorText: { fontSize: 11, color: '#e74c3c', marginTop: 2 },
  status: { fontSize: 12, flexShrink: 0 },
});
