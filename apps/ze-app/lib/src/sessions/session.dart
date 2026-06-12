class Session {
  const Session({
    required this.id,
    this.title,
    this.preview,
    required this.createdAt,
    required this.lastActiveAt,
  });

  final String id;
  final String? title;
  final String? preview;
  final DateTime createdAt;
  final DateTime lastActiveAt;

  factory Session.fromJson(Map<String, dynamic> j) => Session(
        id: j['id'] as String,
        title: j['title'] as String?,
        preview: j['preview'] as String?,
        createdAt: DateTime.parse(j['created_at'] as String),
        lastActiveAt: DateTime.parse(j['last_active_at'] as String),
      );

  String get displayTitle => title?.isNotEmpty == true ? title! : 'New conversation';
}
