import 'package:flutter_test/flutter_test.dart';
import 'package:siutindei_app/features/search/utils/area_filter_options.dart';
import 'package:siutindei_app/services/bundled_areas_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('bundled home wizard tree exposes region area ids', () async {
    final tree = await BundledAreasService.loadFromHomeWizard();
    final options = leafAreaFilterOptions(tree);

    expect(options, isNotEmpty);
    expect(
      options.map((option) => option.id),
      contains('a1111111-1111-1111-1111-111111111101'),
    );
  });
}
