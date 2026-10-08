import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
// ignore: lines_longer_than_80_chars
import 'package:siutindei_app/features/home_wizard/models/home_wizard_choices.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('parses shared home wizard choices json', () {
    const raw = '''
{
  "version": 1,
  "activityTypes": [
    {
      "id": "workshop",
      "categoryId": "c1111111-1111-1111-1111-111111111101",
      "labels": { "en": "Workshop", "zh-HK": "工作坊" }
    }
  ],
  "ageGroups": [
    {
      "id": "1-3",
      "searchAge": 2,
      "labels": { "en": "1–3 years", "zh-HK": "1–3歲" }
    }
  ],
  "regions": [
    {
      "id": "hong_kong_island",
      "areaId": "a1111111-1111-1111-1111-111111111101",
      "labels": { "en": "Hong Kong Island", "zh-HK": "香港島" }
    }
  ]
}
''';

    final choices = HomeWizardChoices.fromJson(
      jsonDecode(raw) as Map<String, dynamic>,
    );

    expect(choices.activityTypes, hasLength(1));
    expect(choices.ageGroups.first.searchAge, 2);
    expect(choices.regions.first.areaId, isNotEmpty);
  });
}
