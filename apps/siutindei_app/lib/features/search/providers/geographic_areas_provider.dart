import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/geographic_area_models.dart';
import '../../../services/service_providers.dart';

/// Cached geographic area tree for search filters.
final geographicAreasProvider =
    AsyncNotifierProvider<GeographicAreasNotifier, List<GeographicAreaNode>>(
  GeographicAreasNotifier.new,
);

class GeographicAreasNotifier extends AsyncNotifier<List<GeographicAreaNode>> {
  @override
  Future<List<GeographicAreaNode>> build() async {
    final areasService = ref.watch(areasServiceProvider);
    return areasService.getActiveAreaTree();
  }
}
