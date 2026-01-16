#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if(!(cin>>n)) return 0;

    vector<long long> key(n+1);
    vector<int> L(n+1), R(n+1);

    for(int i=1;i<=n;i++) cin>>key[i]>>L[i]>>R[i];

    bool ok=true;

    for(int i=1;i<=n;i++) {

        if(L[i] && key[L[i]]>key[i]) ok=false;

        if(R[i] && key[R[i]]<key[i]) ok=false;

    }

    cout<<(ok?"YES\n":"NO\n");

}
