#include <iostream>
using namespace std;

int main() {
    int a, b, c;
    cin >> a >> b; 
    
    int mn = a;
    if (b < mn) mn = b;
    if (c < mn) mn = c;
    cout << mn;
}