import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/geographic_area.dart';
import '../services/service_providers.dart';
import 'auth_viewmodel.dart';

/// Active geographic area tree for search filters (GET /v1/user/areas).
///
/// Reloads when sign-in state changes. Prefer watching this over calling
/// [GeographicAreaService] directly so the tree stays cached per session.
final geographicAreaTreeProvider = FutureProvider<List<GeographicArea>>((
  ref,
) async {
  ref.watch(authViewModelProvider.select((state) => state.isSignedIn));
  return ref.read(geographicAreaServiceProvider).loadActiveAreaTree();
});
