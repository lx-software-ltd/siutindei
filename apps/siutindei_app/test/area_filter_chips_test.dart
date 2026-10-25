import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:siutindei_app/features/search/widgets/area_filter_chips.dart';
import 'package:siutindei_app/models/geographic_area.dart';
import 'package:siutindei_app/viewmodels/geographic_areas_provider.dart';

List<GeographicArea> _sampleTree() {
  return [
    GeographicArea(
      id: 'country',
      parentId: null,
      name: 'Hong Kong',
      level: 'country',
      active: true,
      displayOrder: 1,
      children: [
        GeographicArea(
          id: 'kowloon',
          parentId: 'country',
          name: 'Kowloon',
          level: 'region',
          active: true,
          displayOrder: 1,
          children: [
            GeographicArea(
              id: 'mk',
              parentId: 'kowloon',
              name: 'Mong Kok',
              level: 'district',
              active: true,
              displayOrder: 1,
            ),
          ],
        ),
        GeographicArea(
          id: 'island',
          parentId: 'country',
          name: 'Hong Kong Island',
          level: 'region',
          active: true,
          displayOrder: 2,
        ),
      ],
    ),
  ];
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AreaFilterChips', () {
    Future<void> pumpChips(
      WidgetTester tester, {
      String? selectedAreaId,
      ValueChanged<String?>? onAreaChanged,
    }) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            geographicAreaTreeProvider.overrideWith((ref) async {
              return _sampleTree();
            }),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: AreaFilterChips(
                selectedAreaId: selectedAreaId,
                onAreaChanged: onAreaChanged ?? (_) {},
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
    }

    testWidgets('shows top-level regions from the area tree', (tester) async {
      await pumpChips(tester);

      expect(find.text('Kowloon'), findsOneWidget);
      expect(find.text('Hong Kong Island'), findsOneWidget);
      expect(find.text('Hong Kong'), findsNothing);
    });

    testWidgets('drills into children and offers back navigation', (
      tester,
    ) async {
      String? selected;

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            geographicAreaTreeProvider.overrideWith((ref) async {
              return _sampleTree();
            }),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: StatefulBuilder(
                builder: (context, setState) {
                  return AreaFilterChips(
                    selectedAreaId: selected,
                    onAreaChanged: (id) => setState(() => selected = id),
                  );
                },
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Kowloon'));
      await tester.pumpAndSettle();

      expect(find.text('Mong Kok'), findsOneWidget);
      expect(find.text('All areas'), findsOneWidget);
      expect(find.text('Back'), findsNothing);

      await tester.tap(find.text('Mong Kok'));
      await tester.pumpAndSettle();

      expect(find.text('Back'), findsOneWidget);

      await tester.tap(find.text('Back'));
      await tester.pumpAndSettle();

      expect(find.text('Mong Kok'), findsOneWidget);
      expect(find.text('Kowloon'), findsNothing);
    });

    testWidgets('clears selection from All areas chip', (tester) async {
      String? selected = 'mk';

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            geographicAreaTreeProvider.overrideWith((ref) async {
              return _sampleTree();
            }),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: StatefulBuilder(
                builder: (context, setState) {
                  return AreaFilterChips(
                    selectedAreaId: selected,
                    onAreaChanged: (id) => setState(() => selected = id),
                  );
                },
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('All areas'), findsOneWidget);

      await tester.tap(find.text('All areas'));
      await tester.pumpAndSettle();

      expect(selected, isNull);
      expect(find.text('Kowloon'), findsOneWidget);
      expect(find.text('All areas'), findsNothing);
    });

    testWidgets('uses a horizontal scroll view for overflow', (tester) async {
      await pumpChips(tester);

      expect(find.byType(SingleChildScrollView), findsOneWidget);
      final scrollView = tester.widget<SingleChildScrollView>(
        find.byType(SingleChildScrollView),
      );
      expect(scrollView.scrollDirection, Axis.horizontal);
    });
  });
}
