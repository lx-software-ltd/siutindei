import 'dart:convert';

import 'package:flutter/services.dart';

/// Localized label map (en + zh-HK).
class WizardLabels {
  const WizardLabels({required this.en, required this.zhHk});

  factory WizardLabels.fromJson(Map<String, dynamic> json) {
    return WizardLabels(
      en: json['en'] as String? ?? '',
      zhHk: json['zh-HK'] as String? ?? '',
    );
  }

  final String en;
  final String zhHk;

  String forLocale(String locale) {
    if (locale == 'zh-HK' && zhHk.isNotEmpty) {
      return zhHk;
    }
    return en;
  }
}

class WizardActivityTypeOption {
  const WizardActivityTypeOption({
    required this.id,
    required this.categoryId,
    required this.labels,
  });

  factory WizardActivityTypeOption.fromJson(Map<String, dynamic> json) {
    return WizardActivityTypeOption(
      id: json['id'] as String,
      categoryId: json['categoryId'] as String,
      labels: WizardLabels.fromJson(json['labels'] as Map<String, dynamic>),
    );
  }

  final String id;
  final String categoryId;
  final WizardLabels labels;
}

class WizardAgeGroupOption {
  const WizardAgeGroupOption({
    required this.id,
    required this.searchAge,
    required this.labels,
  });

  factory WizardAgeGroupOption.fromJson(Map<String, dynamic> json) {
    return WizardAgeGroupOption(
      id: json['id'] as String,
      searchAge: json['searchAge'] as int,
      labels: WizardLabels.fromJson(json['labels'] as Map<String, dynamic>),
    );
  }

  final String id;
  final int searchAge;
  final WizardLabels labels;
}

class WizardRegionOption {
  const WizardRegionOption({
    required this.id,
    required this.areaId,
    required this.labels,
  });

  factory WizardRegionOption.fromJson(Map<String, dynamic> json) {
    return WizardRegionOption(
      id: json['id'] as String,
      areaId: json['areaId'] as String,
      labels: WizardLabels.fromJson(json['labels'] as Map<String, dynamic>),
    );
  }

  final String id;
  final String areaId;
  final WizardLabels labels;
}

class HomeWizardChoices {
  const HomeWizardChoices({
    required this.activityTypes,
    required this.ageGroups,
    required this.regions,
  });

  factory HomeWizardChoices.fromJson(Map<String, dynamic> json) {
    final activityTypesJson = json['activityTypes'] as List<dynamic>? ?? [];
    final ageGroupsJson = json['ageGroups'] as List<dynamic>? ?? [];
    final regionsJson = json['regions'] as List<dynamic>? ?? [];
    return HomeWizardChoices(
      activityTypes: activityTypesJson
          .map(
            (item) =>
                WizardActivityTypeOption.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
      ageGroups: ageGroupsJson
          .map(
            (item) =>
                WizardAgeGroupOption.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
      regions: regionsJson
          .map(
            (item) => WizardRegionOption.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
    );
  }

  final List<WizardActivityTypeOption> activityTypes;
  final List<WizardAgeGroupOption> ageGroups;
  final List<WizardRegionOption> regions;

  static Future<HomeWizardChoices> loadFromAsset() async {
    final raw = await rootBundle.loadString(
      'assets/home_wizard/home_wizard_choices.json',
    );
    final json = jsonDecode(raw) as Map<String, dynamic>;
    return HomeWizardChoices.fromJson(json);
  }
}
