import 'package:flutter_test/flutter_test.dart';
import 'package:siutindei_app/domain/entities/activity.dart';

void main() {
  const currency = 'HKD';

  PricingEntity price(double amount, [double? amountMax]) {
    return PricingEntity(
      type: PricingType.perClass,
      amount: amount,
      amountMax: amountMax,
      currency: currency,
    );
  }

  test('prints a range in whole dollars', () {
    expect(price(200, 300).formattedPrice, '200–300 HKD/class');
  });

  test('keeps cents when whole dollars would look the same', () {
    expect(price(199.6, 200.4).formattedPrice, '199.60–200.40 HKD/class');
  });

  test('prints one price when there is no upper bound', () {
    expect(price(200).formattedPrice, '200 HKD/class');
  });
}
