#include <stdio.h>
#include <math.h>
float unit_price(const float pack_price, const int rolls_count, const int pieces_count);
int main() {
    float result = unit_price(4.00, 2, 100);
    if (fabs(result - 2.00) < 0.01) {
        printf("TASK:unit_price=1\n");
    } else {
        printf("TASK:unit_price=0\n");
    }
    return 0;
}
