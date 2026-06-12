import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:ze_app/src/config/app_config.dart';
import 'package:ze_app/src/sessions/session.dart';

class SessionRepository {
  Future<List<Session>> list(AppConfig config) async {
    final uri = Uri.parse('${config.serverUrl}/api/sessions');
    final response = await http.get(uri, headers: {'X-API-Key': config.apiKey});
    if (response.statusCode != 200) return [];
    final data = jsonDecode(response.body) as List<dynamic>;
    return data.map((e) => Session.fromJson(e as Map<String, dynamic>)).toList();
  }
}
