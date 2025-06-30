#include <stdio.h>
#include <math.h>
float lift_a_car(const int stick_length, const int human_weight, const int car_weight);
int main() {
    float result = lift_a_car(2, 80, 1400);
    if (fabs(result - 0.22) < 0.01) {
        printf("TASK:lift_a_car=1\n");
    } else {
        printf("TASK:lift_a_car=0\n");
    }
    return 0;
}
