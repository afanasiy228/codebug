#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,k;
    if(!(cin>>n>>k)) return 0;
    vector<long long>a(n);
    for(int i=0;i<n;i++) cin>>a[i];

    for(int i=0;i+k<=n;i++) {
        long long mx = *min_element(a.begin()+i, a.begin()+i+k);

        if(i) cout<<" ";
        cout<<mx;
    }

    cout<<"\n";

}
