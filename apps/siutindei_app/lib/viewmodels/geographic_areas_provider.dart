import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/geographic_area.dart';
import '../services/service_providers.dart';
import 'auth_viewmodel.dart';

final geographicAreaTreeProvider =
    FutureProvider<List<GeographicArea>>((ref) async {
  ref.watch(authViewModelProvider.select((state) => state.isSignedIn));
  return ref.read(geographicAreaServiceProvider).loadActiveAreaTree();
});
