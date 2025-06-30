#include <stdio.h>
int array_min(const int input_array[], const int arrays_size);
int main() {
    int arr[5] = {1, 5, 3, 2, 4};
    int res = array_min(arr, 5);
    if (res == 1) {
        printf("TASK:array_min=1\n");
    } else {
        printf("TASK:array_min=0\n");
    }
    return 0;
}
