#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if(!(cin>>n)) return 0;
    vector<long long>a(n);
    for(int i=0;i<n;i++) cin>>a[i];

    long long cnt=0;
    for(int i=0;i<n;i++) for(int j=i+1;j<n;j++) if(a[i]>=a[j]) cnt++;

    cout<<cnt<<"\n";

}
