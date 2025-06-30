#include <stdio.h>
#include <math.h>

float lift_a_car(const int stick_length, const int human_weight, const int car_weight);
float unit_price(const float pack_price, const int rolls_count, const int pieces_count);
int collatz(const int number);

int main() {
    int points = 0, max = 3;

    // TEST 1: lift_a_car
    if (fabs(lift_a_car(2, 80, 1400) - 0.22) < 0.01) {
        printf("TASK:lift_a_car=1\n"); points++;
    } else {
        printf("TASK:lift_a_car=0\n");
    }

    // TEST 2: unit_price
    if (fabs(unit_price(4.00, 2, 100) - 2.00) < 0.01) {
        printf("TASK:unit_price=1\n"); points++;
    } else {
        printf("TASK:unit_price=0\n");
    }

    // TEST 3: collatz
    if (collatz(6) == 9) {
        printf("TASK:collatz=1\n"); points++;
    } else {
        printf("TASK:collatz=0\n");
    }

    printf("SUMMARY:%d/%d\n", points, max);
    return 0;
}
