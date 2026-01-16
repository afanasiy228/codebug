#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,m;
    if(!(cin>>n>>m)) return 0;
    vector<vector<pair<int,int>>> g(n);

    for(int i=0;i<m;i++) {
        int u,v,w;
        cin>>u>>v>>w;
        --u;
        --v;
        g[u].push_back( {
            v,w
        }
        );
    }

    const long long INF=4e18;
    vector<long long> d(n, INF);
    d[0]=0;


    for(int v=0; v<n; v++) for(auto [to,w]: g[v]) d[to]=min(d[to], d[v]+w);

    cout<<(d[n-1]>=INF?-1:d[n-1])<<"\n";

}
