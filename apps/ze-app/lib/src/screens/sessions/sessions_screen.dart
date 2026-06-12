import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ze_app/src/config/app_config.dart';
import 'package:ze_app/src/sessions/session.dart';
import 'package:ze_app/src/sessions/session_repository.dart';
import 'package:ze_app/src/ws/providers.dart';

final _sessionsProvider = FutureProvider.autoDispose<List<Session>>((ref) async {
  final config = await ref.watch(appConfigProvider.future);
  if (config == null) return [];
  return SessionRepository().list(config);
});

class SessionsScreen extends ConsumerWidget {
  const SessionsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sessionsAsync = ref.watch(_sessionsProvider);
    final currentThreadId = ref.watch(wsStateProvider).currentThreadId;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Conversations'),
        actions: [
          IconButton(
            tooltip: 'New conversation',
            icon: const Icon(Icons.edit_outlined),
            onPressed: () {
              ref.read(wsClientProvider.notifier).newSession();
              context.go('/');
            },
          ),
        ],
      ),
      body: sessionsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Could not load conversations: $e')),
        data: (sessions) {
          if (sessions.isEmpty) {
            return const _EmptyState();
          }
          return ListView.separated(
            padding: const EdgeInsets.symmetric(vertical: 8),
            itemCount: sessions.length,
            separatorBuilder: (_, __) => const Divider(height: 1, indent: 16, endIndent: 16),
            itemBuilder: (context, i) {
              final session = sessions[i];
              final isActive = session.id == currentThreadId;
              return _SessionTile(
                session: session,
                isActive: isActive,
                onTap: () async {
                  await ref.read(wsClientProvider.notifier).switchSession(session.id);
                  if (context.mounted) context.go('/');
                },
              );
            },
          );
        },
      ),
    );
  }
}

class _SessionTile extends StatelessWidget {
  const _SessionTile({
    required this.session,
    required this.isActive,
    required this.onTap,
  });

  final Session session;
  final bool isActive;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final now = DateTime.now();
    final diff = now.difference(session.lastActiveAt);
    final timeLabel = _formatTime(diff, session.lastActiveAt);

    return ListTile(
      leading: CircleAvatar(
        backgroundColor: isActive ? colors.primaryContainer : colors.surfaceVariant,
        child: Icon(
          Icons.chat_bubble_outline,
          size: 18,
          color: isActive ? colors.onPrimaryContainer : colors.onSurfaceVariant,
        ),
      ),
      title: Text(
        session.displayTitle,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: theme.textTheme.bodyMedium?.copyWith(
          fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
        ),
      ),
      subtitle: session.preview != null
          ? Text(
              session.preview!,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodySmall?.copyWith(color: colors.onSurfaceVariant),
            )
          : null,
      trailing: Text(
        timeLabel,
        style: theme.textTheme.labelSmall?.copyWith(color: colors.onSurfaceVariant),
      ),
      selected: isActive,
      onTap: onTap,
    );
  }

  String _formatTime(Duration diff, DateTime time) {
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${time.day}/${time.month}/${time.year}';
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.chat_bubble_outline, size: 64, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 16),
            const Text('No previous conversations'),
            const SizedBox(height: 8),
            Text(
              'Start chatting to see your history here.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      );
}
