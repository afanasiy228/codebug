#include <bits/stdc++.h>
using namespace std;

long long gcdll(long long a,long long b) {
    while(b) {
        a%=b;
        swap(a,b);
    }
    return a;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long a,b;
    if(!(cin>>a>>b)) return 0;

    long long g = gcdll(a,b-1);

    long long l = a / g * b;

    cout<<l<<"\n";

}
