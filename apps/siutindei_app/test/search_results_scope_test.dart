import 'package:flutter_test/flutter_test.dart';
import 'package:siutindei_app/domain/entities/search.dart';
import 'package:siutindei_app/models/activity_models.dart';

void main() {
  test('fromJson keeps a missing area_scope distinct from null', () {
    final omitted = ActivitySearchResponse.fromJson({
      'items': <dynamic>[],
      'next_cursor': 'cursor-1',
    });
    final unrestricted = ActivitySearchResponse.fromJson({
      'items': <dynamic>[],
      'area_scope': null,
    });
    final limited = ActivitySearchResponse.fromJson({
      'items': <dynamic>[],
      'area_scope': ['mk'],
    });

    expect(omitted.statesAreaScope, isFalse);
    expect(unrestricted.statesAreaScope, isTrue);
    expect(unrestricted.areaScope, isNull);
    expect(limited.areaScope, ['mk']);
  });

  test('a later page keeps the first area scope', () {
    const first = SearchResultsEntity(
      items: [],
      areaScope: ['mk'],
      areaScopeStated: true,
    );
    const next = SearchResultsEntity(
      items: [],
      nextCursor: 'cursor-2',
    );

    final merged = first.mergedWith(next);

    expect(merged.areaScope, ['mk']);
    expect(merged.areaScopeStated, isTrue);
    expect(merged.nextCursor, 'cursor-2');
  });
}
