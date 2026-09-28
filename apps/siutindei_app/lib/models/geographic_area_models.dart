/// Geographic area tree models (GET /v1/user/areas).
class GeographicAreaNode {
  const GeographicAreaNode({
    required this.id,
    required this.name,
    required this.nameTranslations,
    required this.level,
    required this.active,
    required this.displayOrder,
    this.parentId,
    this.code,
    this.children = const [],
  });

  factory GeographicAreaNode.fromJson(Map<String, dynamic> json) {
    final childrenJson = json['children'] as List<dynamic>? ?? [];
    return GeographicAreaNode(
      id: json['id'] as String,
      parentId: json['parent_id'] as String?,
      name: json['name'] as String,
      nameTranslations: Map<String, String>.from(
        (json['name_translations'] as Map<String, dynamic>? ?? {}).map(
          (key, value) => MapEntry(key.toString(), value.toString()),
        ),
      ),
      level: json['level'] as String,
      code: json['code'] as String?,
      active: json['active'] as bool? ?? true,
      displayOrder: json['display_order'] as int? ?? 0,
      children: childrenJson
          .map(
            (child) => GeographicAreaNode.fromJson(
              child as Map<String, dynamic>,
            ),
          )
          .toList(),
    );
  }

  final String id;
  final String? parentId;
  final String name;
  final Map<String, String> nameTranslations;
  final String level;
  final String? code;
  final bool active;
  final int displayOrder;
  final List<GeographicAreaNode> children;

  String labelForLocale(String locale) {
    if (locale == 'zh-HK') {
      final zh = nameTranslations['zh'] ?? nameTranslations['zh-HK'];
      if (zh != null && zh.isNotEmpty) {
        return zh;
      }
    }
    return nameTranslations['en'] ?? name;
  }
}

class AreaTreeResponse {
  const AreaTreeResponse({required this.items});

  factory AreaTreeResponse.fromJson(Map<String, dynamic> json) {
    final itemsJson = json['items'] as List<dynamic>? ?? [];
    return AreaTreeResponse(
      items: itemsJson
          .map(
            (item) => GeographicAreaNode.fromJson(
              item as Map<String, dynamic>,
            ),
          )
          .toList(),
    );
  }

  final List<GeographicAreaNode> items;
}
