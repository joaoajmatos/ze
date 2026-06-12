import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import 'package:ze_app/src/config/app_config.dart';
import 'package:ze_app/src/messages/message.dart';
import 'package:ze_app/src/messages/message_repository.dart';
import 'package:ze_app/src/ws/ws_client.dart';
import 'package:ze_app/src/ws/ws_protocol.dart';

// ── AppConfig provider ─────────────────────────────────────────────────────────

final appConfigProvider = FutureProvider<AppConfig?>((ref) => AppConfig.load());

// ── WebSocket state ────────────────────────────────────────────────────────────

enum WsStatus { connecting, connected, disconnected }

class WsState {
  const WsState({
    this.status = WsStatus.connecting,
    this.messages = const [],
    this.overlayMessages = const [],
    this.isThinking = false,
    this.currentThreadId = 'app-main',
  });

  final WsStatus status;
  final List<Message> messages;
  final List<Message> overlayMessages;
  final bool isThinking;
  final String currentThreadId;

  bool get isConnected => status == WsStatus.connected;

  WsState copyWith({
    WsStatus? status,
    List<Message>? messages,
    List<Message>? overlayMessages,
    bool? isThinking,
    String? currentThreadId,
  }) =>
      WsState(
        status: status ?? this.status,
        messages: messages ?? this.messages,
        overlayMessages: overlayMessages ?? this.overlayMessages,
        isThinking: isThinking ?? this.isThinking,
        currentThreadId: currentThreadId ?? this.currentThreadId,
      );
}

class WsClientNotifier extends StateNotifier<WsState> {
  WsClientNotifier(this._config) : super(const WsState()) {
    _repo = MessageRepository();
    _client = ZeWebSocketClient(config: _config);
    _init();
  }

  final AppConfig _config;
  late ZeWebSocketClient _client;
  late MessageRepository _repo;
  StreamSubscription<InboundFrame>? _sub;

  String get _threadId => state.currentThreadId;

  Future<void> _init() async {
    await _client.connect();
    state = state.copyWith(status: WsStatus.connected);
    _sub = _client.frames.listen(_handleFrame, onError: (_) {
      state = state.copyWith(status: WsStatus.disconnected);
    });
    await _repo.loadHistory(_config);
    _refresh();
    final unread = _repo.unreadAssistantIds;
    if (unread.isNotEmpty) _client.send(AckFrame(ids: unread));
  }

  void _handleFrame(InboundFrame frame) {
    switch (frame) {
      case MessageFrame(message: final m):
        if (m.threadId == null || m.threadId == _threadId) {
          _repo.add(m);
          state = state.copyWith(messages: _repo.messages, isThinking: false, status: WsStatus.connected);
        }
      case TypingFrame():
        state = state.copyWith(isThinking: true);
      case EditFrame(id: final id, text: final text, components: final comps):
        final existing = _repo.messages.firstWhere(
          (m) => m.id == id,
          orElse: () => Message(id: id, role: MessageRole.assistant, text: text, createdAt: DateTime.now()),
        );
        _repo.update(
          id,
          Message(id: id, role: existing.role, text: text ?? existing.text, createdAt: existing.createdAt, components: comps),
        );
        state = state.copyWith(messages: _repo.messages);
      case RefreshFrame():
        break;
      case ErrorFrame():
        state = state.copyWith(isThinking: false);
      case _:
        break;
    }
  }

  void sendMessage(String text, {Map<String, String>? context}) {
    _client.send(SendMessageFrame(text: text, threadId: _threadId, context: context));
    final msg = Message(
      id: 'local_${DateTime.now().millisecondsSinceEpoch}',
      role: MessageRole.user,
      text: text,
      createdAt: DateTime.now(),
      threadId: _threadId,
    );
    _repo.add(msg);
    state = state.copyWith(messages: _repo.messages, isThinking: true);
  }

  void sendCommand(String name) {
    _client.send(CommandFrame(name: name));
    state = state.copyWith(isThinking: true);
  }

  void submitComponent({
    required String sessionId,
    required String stepId,
    required String componentId,
    required Map<String, dynamic> values,
  }) {
    _client.send(ComponentSubmitFrame(
      sessionId: sessionId,
      stepId: stepId,
      componentId: componentId,
      values: values,
    ));
    state = state.copyWith(isThinking: true);
  }

  /// Start a fresh conversation thread. Clears messages and generates a new thread ID.
  void newSession() {
    final threadId = 'app-${const Uuid().v4()}';
    _repo.clear();
    state = state.copyWith(
      messages: const [],
      currentThreadId: threadId,
      isThinking: false,
    );
  }

  /// Switch to a previously recorded session, loading its message history.
  Future<void> switchSession(String threadId) async {
    _repo.clear();
    state = state.copyWith(
      messages: const [],
      currentThreadId: threadId,
      isThinking: false,
    );
    final msgs = await _repo.loadForThread(_config, threadId);
    _repo.addAll(msgs);
    state = state.copyWith(messages: _repo.messages);
  }

  void _refresh() => state = state.copyWith(messages: _repo.messages);

  @override
  void dispose() {
    _sub?.cancel();
    _client.dispose();
    super.dispose();
  }
}

final wsClientProvider = StateNotifierProvider<WsClientNotifier, WsState>((ref) {
  final config = ref.watch(appConfigProvider).valueOrNull;
  if (config == null) {
    return WsClientNotifier(AppConfig(serverUrl: '', apiKey: ''));
  }
  return WsClientNotifier(config);
});

final wsStateProvider = Provider<WsState>((ref) => ref.watch(wsClientProvider));
