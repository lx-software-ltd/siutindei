import '../features/home_wizard/models/home_wizard_choices.dart';
import '../models/geographic_area_models.dart';

/// Offline fallback area tree when the user areas API is unavailable.
class BundledAreasService {
  BundledAreasService._();

  static Future<List<GeographicAreaNode>> loadFromHomeWizard() async {
    final choices = await HomeWizardChoices.loadFromAsset();
    final regions = choices.regions;
    if (regions.isEmpty) {
      return const [];
    }

    return [
      GeographicAreaNode(
        id: 'bundled-hong-kong',
        name: 'Hong Kong',
        nameTranslations: const {'en': 'Hong Kong'},
        level: 'country',
        code: 'HK',
        active: true,
        displayOrder: 0,
        children: regions
            .asMap()
            .entries
            .map(
              (entry) => GeographicAreaNode(
                id: entry.value.areaId,
                parentId: 'bundled-hong-kong',
                name: entry.value.labels.en,
                nameTranslations: {
                  'en': entry.value.labels.en,
                  'zh-HK': entry.value.labels.zhHk,
                },
                level: 'region',
                active: true,
                displayOrder: entry.key,
              ),
            )
            .toList(),
      ),
    ];
  }
}
